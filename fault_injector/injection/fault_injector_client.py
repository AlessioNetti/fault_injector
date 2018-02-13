import logging, signal
from fault_injector.network.client import Client
from fault_injector.network.msg_builder import MessageBuilder
from fault_injector.util.config_tools import ConfigLoader
from fault_injector.util.misc import formatipport
from fault_injector.io.writer import ExecutionLogWriter
from fault_injector.io.reader import Reader
from os.path import splitext, basename
from time import sleep, time


class InjectorClient:
    """
    This class implement the fault injection client

    This entity controls the fault injection process: that is, it reads fault entries from an input workload, issues
    start commands for tasks to remove InjectorServers, and stores the results of task executions to separate logs
    for each connected host
    """

    # Logger for the class
    logger = logging.getLogger(__name__)

    def __init__(self, clientobj, workload_padding=20, pre_send_interval=600, session_wait=60, results_dir='results'):
        """
        Constructor for the class

        :param clientobj: Client object for remote communication
        :param workload_padding: Time in seconds to be added at the start of the workload as padding, in order to keep
            the system in idle state for a short time and prevent perturbation in the data
        :param pre_send_interval: Time in seconds specifying the interval of time between sending a task start command,
            and its actual starting time. With the default settings, task start commands are sent 10 minutes before
            their scheduled start time
        :param session_wait: Time in seconds defining the interval of time in which to wait for all connected hosts
            to reply during the initialization and finalization of the session
        :param results_dir: Path of the results' directory, where the execution logs will be saved
        """
        assert isinstance(clientobj, Client), 'InjectorClient needs a Client object in its constructor!'
        self._client = clientobj
        self._workloadPadding = workload_padding
        self._preSendInterval = pre_send_interval
        self._resultsDir = results_dir
        self._sessionWait = session_wait
        # Sleep period of the busy loop in the _inject method
        self._sleepPeriod = 0.5
        # The interval used for sending clock correction messages to connected hosts
        self._clockCorrectionPeriod = 30
        # A dictionary with (ip, port) keys, and values representing the Writer objects for execution logs associated
        # to each host
        self._writers = None
        # Also a dictionary with (ip, port) keys: each entry is a set containing the sequence numbers for tasks from
        # which we are waiting response on remote hosts
        self._pendingTasks = None
        self._reader = None
        # We register the signal handler for termination requested by the user
        signal.signal(signal.SIGINT, self._signalhandler)

    @staticmethod
    def build(config=None, hosts=None):
        """
        Static method that automatically builds an InjectorClient object starting from a given configuration file

        :param config: The path to the json configuration file
        :param hosts: the list of hosts as ip:port strings. This list has priority over the hosts specified in the input
            configuration file
        :return: An InjectionClient object
        """
        cfg = ConfigLoader.getConfig(config)
        cl = Client(socket_timeout=cfg['SOCKET_TIMEOUT'])
        inj_c = InjectorClient(clientobj=cl, workload_padding=cfg['WORKLOAD_PADDING'],
                               pre_send_interval=cfg['PRE_SEND_INTERVAL'], session_wait=cfg['SESSION_WAIT'],
                               results_dir=cfg['RESULTS_DIR'])
        if hosts is None and 'HOSTS' in cfg:
            hosts = cfg['HOSTS']
        # The hosts specified in the configuration file (or as input to the method) are added and connection is
        # established with them
        if hosts is not None:
            if not isinstance(hosts, (list, tuple)):
                hosts = list(hosts)
            cl.add_servers(hosts)
        return inj_c

    def stop(self):
        """
        Stops the injection client
        """
        self._client.stop()

    def inject(self, reader, max_tasks=None):
        """
        Starts the injection process. If no reader to a valid workload is supplied, the client operates in pull mode,
        simply storing the execution records of connected hosts without issuing any command. This is useful to monitor
        currently running injection sessions from different machines

        :param reader: Reader object associated with the input workload
        :param max_tasks: The maximum number of tasks to be processed before terminating. Useful for debugging
        """
        if reader is not None:
            self._inject(reader, max_tasks)
        else:
            self._pull()

    def _inject(self, reader, max_tasks=None):
        """
        Starts the injection process with a given workload, issuing commands to start tasks on remote hosts and
        collecting their result

        :param reader: a valid Reader object
        :param max_tasks: The maximum number of tasks to be processed before terminating. Useful for debugging
        """
        self._reader = reader
        assert isinstance(reader, Reader), '_inject method only supports Reader objects!'
        task = reader.read_entry()
        if task is None:
            InjectorClient.logger.warning("Input workload appears to be empty. Aborting...")
            return

        self._client.start()

        # Initialized the injection session
        session_accepted = self._init_session(workload_name=splitext(basename(reader.get_path()))[0])
        if session_accepted == 0:
            InjectorClient.logger.warning("No valid hosts for injection detected. Aborting...")
            return

        # Determines if we have reached the end of the workload
        end_reached = False
        read_tasks = 0

        # Timestamp of the last correction that was applied to the clock of remote hosts
        last_clock_correction = time()
        # Start timestamp for the workload, computed from its first entry, minus the specified padding value
        start_timestamp = task.timestamp - self._workloadPadding
        # Synchronizes the time with all of the connected hosts
        msg = MessageBuilder.command_set_time(start_timestamp)
        self._client.broadcast_msg(msg)
        # Absolute timestamp associated to the workload's starting timestamp
        start_timestamp_abs = time()

        while not end_reached or self._tasks_are_pending():
            # While some tasks are still running, and there are tasks from the workload that still need to be read, we
            # keep looping
            while self._client.peek_msg_queue() > 0:
                # We process all messages in the input queue, and write their content to the execution log for the
                # given host
                addr, msg = self._client.pop_msg_queue()
                self._writers[addr].write_entry(msg)
                msg_type = msg[MessageBuilder.FIELD_TYPE]
                # We log on the terminal the content of the message in a pretty form
                if msg_type == MessageBuilder.STATUS_START:
                    InjectorClient.logger.info("Task %s started on host %s" % (msg[MessageBuilder.FIELD_DATA], formatipport(addr)))
                elif msg_type == MessageBuilder.STATUS_END:
                    InjectorClient.logger.info("Task %s terminated successfully on host %s" % (
                        msg[MessageBuilder.FIELD_DATA], formatipport(addr)))
                    # If a task terminates, we remove its sequence number from the set of pending tasks for the host
                    self._pendingTasks[addr].discard(msg[MessageBuilder.FIELD_SEQNUM])
                elif msg_type == MessageBuilder.STATUS_ERR:
                    InjectorClient.logger.warning("Task %s terminated with error code %s on host %s" % (
                        msg[MessageBuilder.FIELD_DATA], str(msg[MessageBuilder.FIELD_ERR]), formatipport(addr)))
                    self._pendingTasks[addr].discard(msg[MessageBuilder.FIELD_SEQNUM])

            # We compute the new "virtual" timestamp, in function of the workload's starting time
            now_timestamp_abs = time()
            now_timestamp = start_timestamp + (now_timestamp_abs - start_timestamp_abs)

            # We perform periodically a correction of the clock of the remote hosts. This has impact only when there
            # is a very large drift between the clocks, of several minutes
            if now_timestamp_abs - last_clock_correction > self._clockCorrectionPeriod:
                msg = MessageBuilder.command_correct_time(now_timestamp)
                self._client.broadcast_msg(msg)
                last_clock_correction = now_timestamp_abs

            while not end_reached and task.timestamp < now_timestamp + self._preSendInterval:
                # We read all entries from the workload that correspond to tasks scheduled to start in the next
                # minutes (specified by presendinterval), and issue the related commands. This supposes that the
                # workload entries are ordered by their timestamp
                msg = MessageBuilder.command_start(task.args, task.duration, task.seqNum, task.timestamp, task.isFault)
                self._client.broadcast_msg(msg)
                for s in self._pendingTasks.values():
                    s.add(task.seqNum)
                task = reader.read_entry()
                read_tasks += 1
                if task is None or (max_tasks is not None and read_tasks >= max_tasks):
                    end_reached = True
                    reader.close()

            # If the number of hosts from which we are waiting replies is higher than the number of connected hosts
            # (as computed by the Client) object, it means we have lost connectivity with some hosts. Therefore, we
            # remove them. The writer objects are instead kept open because there might still be spurious messages
            # awaiting to be popped from the input queue, from said hots
            if len(self._pendingTasks) > self._client.get_n_registered_hosts():
                self._remove_disconnected_hosts()

            # This is a busy loop, with a short sleep period of roughly one second
            sleep(self._sleepPeriod)

        self._end_session()

    def _pull(self):
        """
        Starts the injection server in pull mode: that is, no workload is injected, and the execution logs are stored
        as messages are sent from the connected hosts.
        """
        self._client.start()

        msg = MessageBuilder.command_greet(0)
        self._client.broadcast_msg(msg)

        addrs = self._client.get_registered_hosts()
        self._writers = {}
        for addr in addrs:
            # We create an execution log writer for each connected host
            path = self._resultsDir + '/listening-' + addr[0] + '_' + str(addr[1]) + '.csv'
            self._writers[addr] = ExecutionLogWriter(path)

        while True:
            # The loop does not end; it is up to users to terminate the listening process by killing the process
            addr, msg = self._client.pop_msg_queue()
            # Messages are popped from the input queue, and their content stored
            self._writers[addr].write_entry(msg)
            msg_type = msg[MessageBuilder.FIELD_TYPE]
            if msg_type == MessageBuilder.STATUS_START:
                InjectorClient.logger.info("Task %s started on host %s" % (msg[MessageBuilder.FIELD_DATA], formatipport(addr)))
            elif msg_type == MessageBuilder.STATUS_END:
                InjectorClient.logger.info("Task %s terminated successfully on host %s" % (
                    msg[MessageBuilder.FIELD_DATA], formatipport(addr)))
            elif msg_type == MessageBuilder.STATUS_ERR:
                InjectorClient.logger.warning("Task %s terminated with error code %s on host %s" % (
                    msg[MessageBuilder.FIELD_DATA], str(msg[MessageBuilder.FIELD_ERR]), formatipport(addr)))
            elif msg_type == MessageBuilder.STATUS_GREET:
                InjectorClient.logger.info("Greetings. Host %s is alive with %s currently active tasks" % (
                    formatipport(addr), str(msg[MessageBuilder.FIELD_DATA])))

    def _init_session(self, workload_name):
        """
        Initializes the injection session for all connected hosts

        :param workload_name: The name of the workload to be injected
        :return: the number of hosts that have accepted the injection start command
        """
        msg_start = MessageBuilder.command_session(time())
        self._client.broadcast_msg(msg_start)

        self._writers = {}
        self._pendingTasks = {}
        session_accepted = 0
        session_replied = 0
        session_sent = self._client.get_n_registered_hosts()
        session_check_start = time()
        session_check_now = time()
        while session_check_now - session_check_start < self._sessionWait and session_replied < session_sent:
            # We wait until we receive an ack (positive or negative) from all connected hosts, or either we time out
            if self._client.peek_msg_queue() > 0:
                addr, msg = self._client.pop_msg_queue()
                if msg[MessageBuilder.FIELD_TYPE] == MessageBuilder.ACK_YES:
                    # If an host replies to the injection start command with a positive ack, its log writer is
                    # instantiated, together with its entry in the pendingTasks dictionary
                    InjectorClient.logger.info("Injection session started with host %s" % formatipport(addr))
                    session_accepted += 1
                    session_replied += 1
                    path = self._resultsDir + '/injection-' + workload_name + '-' + addr[0] + '_' + str(addr[1]) + '.csv'
                    self._writers[addr] = ExecutionLogWriter(path)
                    self._writers[addr].write_entry(msg_start)
                    self._pendingTasks[addr] = set()
                elif msg[MessageBuilder.FIELD_TYPE] == MessageBuilder.ACK_NO:
                    # If an host rejects the injection start command, we discard it
                    InjectorClient.logger.warning("Injection session request rejected by host %s" % formatipport(addr))
                    session_replied += 1
                    self._client.remove_host(addr)
            sleep(self._sleepPeriod)
            session_check_now = time()

        if session_check_now - session_check_start >= self._sessionWait:
            # If we have reached the time out, it means that not all of the connected hosts have replied. This is
            # highly unlikely, but could still happen. In this case, we remove all hosts that have not replied
            InjectorClient.logger.warning("Injection session startup reached the timeout limit")
            for addr in self._client.get_registered_hosts():
                if addr not in self._writers:
                    self._client.remove_host(addr)

        return session_accepted

    def _end_session(self):
        """
        Terminates the injection session for all connected hosts
        """
        msg_end = MessageBuilder.command_session(time(), end=True)
        self._client.broadcast_msg(msg_end)

        session_closed = 0
        session_sent = self._client.get_n_registered_hosts()
        session_check_start = time()
        session_check_now = time()
        while session_check_now - session_check_start < self._sessionWait and session_closed < session_sent:
            # We wait until we have received an ack for the termination from all of the connected hosts, or we time out
            if self._client.peek_msg_queue() > 0:
                addr, msg = self._client.pop_msg_queue()
                if msg[MessageBuilder.FIELD_TYPE] == MessageBuilder.ACK_YES:
                    InjectorClient.logger.info("Injection session closed with host %s" % formatipport(addr))
                    self._writers[addr].write_entry(msg_end)
                    session_closed += 1
                else:
                    # If we receive a message that is not an ack after all tasks have terminated, something is wrong
                    InjectorClient.logger.error("Ack expected from host %s, got %s" % (formatipport(addr), msg[MessageBuilder.FIELD_TYPE]))
            sleep(self._sleepPeriod)
            session_check_now = time()

        # All of the execution log writers are closed, and the session finishes
        for writer in self._writers.values():
            writer.close()

    def _tasks_are_pending(self):
        """
        Detects if there are some remote tasks that are still to finish

        :return: True if there are pending tasks, False otherwise
        """
        if self._pendingTasks is not None:
            for s in self._pendingTasks.values():
                # If the set of Task sequence number is not empty for at least one connected host, it means there are
                # pending tasks, and we return
                if len(s) > 0:
                    return True
        return False

    def _remove_disconnected_hosts(self):
        """
        Removes disconnected hosts from those considered for execution log recording and for sending tasks
        """
        hosts = self._client.get_registered_hosts()
        writers = list(self._writers.keys())
        for addr in writers:
            # If an host that is being considered for the injection process is not present in the list of currently
            # connected hosts (managed by MessageEntity), we remove it
            if addr not in hosts:
                # self._writers[addr].close()
                # self._writers.pop(addr, None)
                self._pendingTasks.pop(addr, None)

    def _signalhandler(self, sig, frame):
        """
        A signal handler to perform a graceful exit procedure on SIGINT 
        """
        if sig == signal.SIGINT:
            if self._writers is not None:
                for w in self._writers.values():
                    w.close()
            if self._reader is not None:
                self._reader.close()
            InjectorClient.logger.info('Exit requested by user. Cleaning up...')
            self._client.stop()
            InjectorClient.logger.info('Injection client stopped by user!')
            exit()
