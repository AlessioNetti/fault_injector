import logging, signal
from fault_injector.network.client import Client
from fault_injector.network.msg_builder import MessageBuilder
from fault_injector.util.config_tools import ConfigLoader
from fault_injector.util.misc import formatipport, strtoaddr
from fault_injector.util.misc import format_injection_filename, format_output_directory, format_output_filename
from fault_injector.io.writer import ExecutionLogWriter
from fault_injector.io.reader import Reader
from os.path import splitext, basename, isdir
from os import mkdir
from time import sleep, time
from shutil import rmtree


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
        self._suppressOutput = False
        self._workloadPadding = workload_padding
        self._preSendInterval = pre_send_interval
        self._resultsDir = results_dir
        self._sessionWait = session_wait
        self._session_id = None
        # Sleep period of the busy loop in the _inject method
        self._sleepPeriod = 0.5
        # The interval used for sending clock correction messages to connected hosts
        self._clockCorrectionPeriod = 30
        # A dictionary with (ip, port) keys, and values representing the Writer objects for execution logs associated
        # to each host
        self._writers = None
        # A dictionary containing the paths where output logs must be stored for each server
        self._outputsDirs = None
        # Also a dictionary with (ip, port) keys: each entry is a set containing the sequence numbers for tasks from
        # which we are waiting response on remote hosts
        self._pendingTasks = None
        self._endReached = False
        self._reader = None
        self._start_timestamp = 0
        self._start_timestamp_now = 0
        # We register the signal handler for termination requested by the user
        signal.signal(signal.SIGINT, self._signalhandler)
        signal.signal(signal.SIGTERM, self._signalhandler)

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
        cl = Client(retry_interval=cfg['RETRY_INTERVAL'], retry_period=cfg['RETRY_PERIOD'], re_send_msgs=cfg['RECOVER_AFTER_DISCONNECT'])
        inj_c = InjectorClient(clientobj=cl, workload_padding=cfg['WORKLOAD_PADDING'], pre_send_interval=cfg['PRE_SEND_INTERVAL'],
                               session_wait=cfg['SESSION_WAIT'], results_dir=cfg['RESULTS_DIR'])
        if hosts is None and 'HOSTS' in cfg:
            hosts = cfg['HOSTS']
        # The hosts specified in the configuration file (or as input to the method) are added and connection is
        # established with them
        if hosts is not None:
            if not isinstance(hosts, (list, tuple)):
                hosts = list(hosts)
            hosts = [strtoaddr(h) for h in hosts if strtoaddr(h) is not None]
            cl.add_servers(hosts)
        return inj_c

    def stop(self):
        """
        Stops the injection client
        """
        self._client.stop()

    def inject(self, reader, max_tasks=None, suppress_output=False):
        """
        Starts the injection process. If no reader to a valid workload is supplied, the client operates in pull mode,
        simply storing the execution records of connected hosts without issuing any command. This is useful to monitor
        currently running injection sessions from different machines

        :param reader: Reader object associated with the input workload
        :param max_tasks: The maximum number of tasks to be processed before terminating. Useful for debugging
        :param suppress_output: If True, all output file writing is suppressed
        """
        self._suppressOutput = suppress_output
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

        # Initializing the injection session
        session_accepted, session_id = self._init_session(workload_name=splitext(basename(reader.get_path()))[0])
        if session_accepted == 0:
            InjectorClient.logger.warning("No valid hosts for injection detected. Aborting...")
            return

        self._session_id = session_id
        # Determines if we have reached the end of the workload
        self._endReached = False
        read_tasks = 0

        # Start timestamp for the workload, computed from its first entry, minus the specified padding value
        self._start_timestamp = task.timestamp - self._workloadPadding
        # Synchronizes the time with all of the connected hosts
        self._client.broadcast_msg(MessageBuilder.command_set_time(self._start_timestamp))
        # Absolute timestamp associated to the workload's starting timestamp
        self._start_timestamp_abs = time()
        # Timestamp of the last correction that was applied to the clock of remote hosts
        last_clock_correction = self._start_timestamp_abs

        while not self._endReached or self._tasks_are_pending():
            # While some tasks are still running, and there are tasks from the workload that still need to be read, we
            # keep looping
            while self._client.peek_msg_queue() > 0:
                # We process all messages in the input queue, and write their content to the execution log for the
                # given host
                addr, msg = self._client.pop_msg_queue()
                self._process_msg_inject(addr, msg)

            # We compute the new "virtual" timestamp, in function of the workload's starting time
            now_timestamp_abs = time()
            now_timestamp = self._get_timestamp(now_timestamp_abs)

            # We perform periodically a correction of the clock of the remote hosts. This has impact only when there
            # is a very large drift between the clocks, of several minutes
            # If the sliding window for the task injection is disabled there is no need to perform clock correction
            if now_timestamp_abs - last_clock_correction > self._clockCorrectionPeriod and self._preSendInterval >= 0:
                msg = MessageBuilder.command_correct_time(now_timestamp)
                self._client.broadcast_msg(msg)
                last_clock_correction = now_timestamp_abs

            while not self._endReached and (task.timestamp < now_timestamp + self._preSendInterval or self._preSendInterval < 0):
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
                    self._endReached = True
                    reader.close()

            # This is a busy loop, with a short sleep period of roughly one second
            sleep(self._sleepPeriod)

        self._end_session()

    def _pull(self):
        """
        Starts the injection server in pull mode: that is, no workload is injected, and the execution logs are stored
        as messages are sent from the connected hosts.
        """
        self._client.start()

        if self._client.get_n_registered_hosts() == 0:
            InjectorClient.logger.warning("No connected hosts for pulling information. Aborting...")
            return

        msg = MessageBuilder.command_greet(0)
        self._client.broadcast_msg(msg)

        addrs = self._client.get_registered_hosts()
        self._writers = {}
        self._outputsDirs = {}
        for addr in addrs:
            self._outputsDirs[addr] = format_output_directory(self._resultsDir, addr)
            # The outputs directory needs to be flushed before starting the new injection session
            if not self._suppressOutput:
                if isdir(self._outputsDirs[addr]):
                    rmtree(self._outputsDirs[addr], ignore_errors=True)
                # We create an execution log writer for each connected host
                self._writers[addr] = ExecutionLogWriter(format_injection_filename(self._resultsDir, addr))

        while True:
            # The loop does not end; it is up to users to terminate the listening process by killing the process
            addr, msg = self._client.pop_msg_queue()
            self._process_msg_pull(addr, msg)

    def _init_session(self, workload_name):
        """
        Initializes the injection session for all connected hosts

        :param workload_name: The name of the workload to be injected
        :return: the number of hosts that have accepted the injection start command, and the timestamp ID of the session
        """
        session_start_timestamp = time()
        msg_start = MessageBuilder.command_session(session_start_timestamp)
        self._client.broadcast_msg(msg_start)

        self._writers = {}
        self._outputsDirs = {}
        self._pendingTasks = {}
        session_accepted = set()
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
                    session_accepted.add(addr)
                    session_replied += 1
                    self._outputsDirs[addr] = format_output_directory(self._resultsDir, addr, workload_name)
                    # The outputs directory needs to be flushed before starting the new injection session
                    if not self._suppressOutput:
                        if isdir(self._outputsDirs[addr]):
                            rmtree(self._outputsDirs[addr], ignore_errors=True)
                        self._writers[addr] = ExecutionLogWriter(format_injection_filename(self._resultsDir, addr, workload_name))
                        self._writers[addr].write_entry(MessageBuilder.command_session(msg[MessageBuilder.FIELD_TIME]))
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
                if addr not in session_accepted:
                    self._client.remove_host(addr)

        return len(session_accepted), session_start_timestamp

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
                    if not self._suppressOutput:
                        self._writers[addr].write_entry(MessageBuilder.command_session(msg[MessageBuilder.FIELD_TIME], end=True))
                    session_closed += 1
                else:
                    # If we receive a message that is not an ack after all tasks have terminated, something is wrong
                    InjectorClient.logger.error("Ack expected from host %s, got %s" % (formatipport(addr), msg[MessageBuilder.FIELD_TYPE]))
            sleep(self._sleepPeriod)
            session_check_now = time()

        # All of the execution log writers are closed, and the session finishes
        if not self._suppressOutput:
            for writer in self._writers.values():
                writer.close()

    def _process_msg_inject(self, addr, msg):
        """
        Processes incoming message for clients involved in an injection session

        :param addr: The address of the sender
        :param msg: The message dictionary
        """
        # We process status messages for connections that are in the queue
        is_status, status = Client.is_status_message(msg)
        if is_status and status == Client.CONNECTION_LOST_MSG:
            # If connection has been lost with an host, we remove its pendingTasks entry
            if not self._suppressOutput:
                self._writers[addr].write_entry(MessageBuilder.status_connection(time()))
        elif is_status and status == Client.CONNECTION_RESTORED_MSG:
            # If connection has been restored with an host, we send a new session start command
            self._client.send_msg(addr, MessageBuilder.command_session(self._session_id))
            self._client.send_msg(addr, MessageBuilder.command_set_time(self._get_timestamp(time())))
        elif is_status and status == Client.CONNECTION_FINALIZED_MSG:
            self._pendingTasks.pop(addr, None)
            # If all connections to servers were finalized we assume that the injection can be terminated
            if len(self._pendingTasks) == 0:
                self._endReached = True
                self._reader.close()
        else:
            msg_type = msg[MessageBuilder.FIELD_TYPE]
            if msg_type != MessageBuilder.ACK_YES and msg_type != MessageBuilder.ACK_NO:
                # Ack messages are not written to the output log
                if not self._suppressOutput:
                    self._writers[addr].write_entry(msg)
            # We log on the terminal the content of the message in a pretty form
            if msg_type == MessageBuilder.STATUS_START:
                InjectorClient.logger.info("Task %s started on host %s" % (msg[MessageBuilder.FIELD_DATA], formatipport(addr)))
            elif msg_type == MessageBuilder.STATUS_END:
                InjectorClient.logger.info("Task %s terminated successfully on host %s" % (msg[MessageBuilder.FIELD_DATA], formatipport(addr)))
                # If a task terminates, we remove its sequence number from the set of pending tasks for the host
                self._pendingTasks[addr].discard(msg[MessageBuilder.FIELD_SEQNUM])
                if not self._suppressOutput:
                    self._write_task_output(addr, msg)
            elif msg_type == MessageBuilder.STATUS_ERR:
                InjectorClient.logger.error("Task %s terminated with error code %s on host %s" % (
                    msg[MessageBuilder.FIELD_DATA], str(msg[MessageBuilder.FIELD_ERR]), formatipport(addr)))
                self._pendingTasks[addr].discard(msg[MessageBuilder.FIELD_SEQNUM])
            elif msg_type == MessageBuilder.ACK_YES:
                # ACK messages after the initialization phase are received ONLY when a connection is restored,
                # and the session must be resumed
                InjectorClient.logger.warning("Session resumed with host %s" % formatipport(addr))
                # If the ack msg contains an error, it means all previously running tasks have been lost
                if not self._suppressOutput:
                    self._writers[addr].write_entry(MessageBuilder.status_connection(time(), restored=True))
                if MessageBuilder.FIELD_ERR in msg:
                    self._pendingTasks[addr] = set()
                    if not self._suppressOutput:
                        self._writers[addr].write_entry(MessageBuilder.status_reset(msg[MessageBuilder.FIELD_TIME]))
            elif msg_type == MessageBuilder.ACK_NO:
                InjectorClient.logger.warning("Session cannot be resumed with host %s" % formatipport(addr))
                self._client.remove_host(addr)

    def _process_msg_pull(self, addr, msg):
        """
        Processes incoming message for clients that are in pull mode, not injecting any fault

        :param addr: The address of the sender
        :param msg: The message dictionary
        """
        # We process status messages for connections that are in the queue
        is_status, status = Client.is_status_message(msg)
        if is_status and status == Client.CONNECTION_LOST_MSG:
            if not self._suppressOutput:
                self._writers[addr].write_entry(MessageBuilder.status_connection(time()))
        elif is_status and status == Client.CONNECTION_RESTORED_MSG:
            if not self._suppressOutput:
                self._writers[addr].write_entry(MessageBuilder.status_connection(time(), restored=True))
        else:
            # Messages are popped from the input queue, and their content stored
            if not self._suppressOutput:
                self._writers[addr].write_entry(msg)
            msg_type = msg[MessageBuilder.FIELD_TYPE]
            if msg_type == MessageBuilder.STATUS_START:
                InjectorClient.logger.info(
                    "Task %s started on host %s" % (msg[MessageBuilder.FIELD_DATA], formatipport(addr)))
            elif msg_type == MessageBuilder.STATUS_END:
                InjectorClient.logger.info("Task %s terminated successfully on host %s" % (
                    msg[MessageBuilder.FIELD_DATA], formatipport(addr)))
                if not self._suppressOutput:
                    self._write_task_output(addr, msg)
            elif msg_type == MessageBuilder.STATUS_ERR:
                InjectorClient.logger.error("Task %s terminated with error code %s on host %s" % (
                    msg[MessageBuilder.FIELD_DATA], str(msg[MessageBuilder.FIELD_ERR]), formatipport(addr)))
            elif msg_type == MessageBuilder.STATUS_GREET:
                status_string = 'An injection session is in progress' if msg[MessageBuilder.FIELD_ISF] else \
                    'No injection session is in progress'
                InjectorClient.logger.info("Greetings. Host %s is alive with %s currently active tasks. %s" % (
                    formatipport(addr), str(msg[MessageBuilder.FIELD_DATA]), status_string))

    def _get_timestamp(self, t):
        """
        Returns the current timestamp in virtual workload time

        :param t: the reference absolute timestamp
        :return: The current timestamp
        """
        return self._start_timestamp + (t - self._start_timestamp_abs)

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

    def _write_task_output(self, addr, msg):
        """
        Given a task end message and an address, writes the related output log.

        This is done only if the output field is present in the message, which happens only for benchmark tasks that
        output to stdout.

        :param addr: The address of the sender
        :param msg: The task end message
        """
        if MessageBuilder.FIELD_OUTPUT not in msg or not isinstance(msg[MessageBuilder.FIELD_OUTPUT], str):
            return
        if not isdir(self._outputsDirs[addr]):
            mkdir(self._outputsDirs[addr])
        output_file = open(format_output_filename(self._outputsDirs[addr], msg), 'w')
        output_file.write(msg[MessageBuilder.FIELD_OUTPUT])
        output_file.close()

    def _signalhandler(self, sig, frame):
        """
        A signal handler to perform a graceful exit procedure on SIGINT 
        """
        if sig == signal.SIGINT or sig == signal.SIGTERM:
            if self._writers is not None and not self._suppressOutput:
                for w in self._writers.values():
                    w.close()
            if self._reader is not None:
                self._reader.close()
            InjectorClient.logger.info('Exit requested by user. Cleaning up...')
            self._client.stop()
            InjectorClient.logger.info('Injection client stopped by user!')
            exit()
