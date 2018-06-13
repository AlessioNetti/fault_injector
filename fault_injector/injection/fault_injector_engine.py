import logging, signal
from time import time
from fault_injector.network.msg_server import MessageServer
from fault_injector.injection.thread_pool import InjectionThreadPool
from fault_injector.network.msg_builder import MessageBuilder
from fault_injector.util.misc import formatipport
from fault_injector.util.config_tools import ConfigLoader
from fault_injector.io.task import Task
from fault_injector.util.subprocess_manager import SubprocessManager


class InjectorEngine:
    """
    This class manages the entire fault injection process, by executing tasks and communicating their outcome
    """

    # Logger for the class
    logger = logging.getLogger('InjectorEngine')

    @staticmethod
    def build(config=None, port=None):
        """
        Static method that automatically builds an InjectorServer object starting from a given configuration file
        
        :param config: The path to the json configuration file
        :param port: Listening port for the server
        :return: An InjectionServer object
        """
        cfg = ConfigLoader.getConfig(config)

        if port is None and 'SERVER_PORT' in cfg:
            port = cfg['SERVER_PORT']

        se = MessageServer(port=port, re_send_msgs=cfg['RECOVER_AFTER_DISCONNECT'])
        pool = InjectionThreadPool(msg_server=se, max_requests=cfg['MAX_REQUESTS'], skip_expired=cfg['SKIP_EXPIRED'],
                                   retry_tasks=cfg['RETRY_TASKS'], retry_on_error=cfg['RETRY_TASKS_ON_ERROR'], log_outputs=cfg['LOG_OUTPUTS'],
                                   root=cfg['ENABLE_ROOT'], numa_cores=(cfg['NUMA_CORES_FAULTS'], cfg['NUMA_CORES_BENCHMARKS']))
        inj_s = InjectorEngine(serverobj=se, poolobj=pool, kill_abruptly=cfg['ABRUPT_TASK_KILL'], aux_commands=cfg['AUX_COMMANDS'])
        return inj_s

    def __init__(self, serverobj, poolobj, kill_abruptly=True, aux_commands=None):
        """
        Constructor for the class
        
        :param serverobj: Server object to be used for communication
        :param poolobj: InjectionThreadPool object to be used
        :param kill_abruptly: Boolean flag. See InjectionThreadPool for details
        :param aux_commands: A list of commands corresponding to subtasks that must be executed alongside the server
        """
        assert isinstance(serverobj, MessageServer), 'InjectorEngine needs a Server object in its constructor!'
        self._server = serverobj
        self._master = None
        self._subman = SubprocessManager(commands=aux_commands)
        self._session_timestamp = -1
        self._kill_abruptly = kill_abruptly
        self._pool = poolobj

    def listen(self):
        """
        Listens for incoming fault injection requests and executes them 
        """
        signal.signal(signal.SIGINT, self._signalhandler)
        signal.signal(signal.SIGTERM, self._signalhandler)
        self._subman.start_subprocesses()
        self._server.start()
        self._pool.start()
        while True:
            # Waiting for a new requests to arrive
            addr, msg = self._server.pop_msg_queue()
            msg_type = msg[MessageBuilder.FIELD_TYPE]
            # If a session command has arrived, we process it accordingly
            if msg_type == MessageBuilder.COMMAND_START_SESSION or msg_type == MessageBuilder.COMMAND_END_SESSION:
                self._update_session(addr, msg)
            # The set time is sent by the master after a successful ack and defines when the 'workload' is started
            elif msg_type == MessageBuilder.COMMAND_SET_TIME and self._master is not None and addr == self._master:
                self._pool.reset_session(msg[MessageBuilder.FIELD_TIME], time())
            # If the master has sent a clock correction request, we process it
            elif msg_type == MessageBuilder.COMMAND_CORRECT_TIME and self._master is not None and addr == self._master:
                self._pool.correct_time(msg[MessageBuilder.FIELD_TIME])
            # Processing a termination command
            elif msg_type == MessageBuilder.COMMAND_TERMINATE:
                self._check_for_termination(addr, msg)
            # If a new command has been issued by the current session master, we add it to the thread pool queue
            elif addr == self._master and msg[MessageBuilder.FIELD_TYPE] == MessageBuilder.COMMAND_START:
                self._pool.submit_task(Task.msg_to_task(msg))
            elif msg_type == MessageBuilder.COMMAND_GREET:
                reply = MessageBuilder.status_greet(time(), self._pool.active_tasks(), self._master is not None)
                self._server.send_msg(addr, reply)
            else:
                InjectorEngine.logger.warning('Invalid command sent from non-master host %s', formatipport(addr))

    def _check_for_termination(self, addr, msg):
        """
        Checks if the input message is valid for the termination of the server
        
        :param addr: Address of the sender as (port, ip)
        :param msg: Input message
        """
        if addr == self._master and msg[MessageBuilder.FIELD_TYPE] == MessageBuilder.COMMAND_TERMINATE:
            self._signalhandler(signal.SIGINT, None)

    def _update_session(self, addr, msg):
        """
        Checks and updates session-related information
        
        In a fault injection session, the master is the only host allowed to issue commands to this server. All other
        connected host can only monitor information
        
        :param addr: The (ip, port) address of the sender host
        :param msg: The message dictionary
        """
        ack = False
        err = None
        if msg[MessageBuilder.FIELD_TYPE] == MessageBuilder.COMMAND_END_SESSION and addr == self._master:
            # If the current master has terminated its session, we react accordingly
            self._master = None
            self._session_timestamp = -1
            ack = True
            InjectorEngine.logger.info('Injection session terminated with controller %s' % formatipport(addr))
        elif msg[MessageBuilder.FIELD_TYPE] == MessageBuilder.COMMAND_START_SESSION:
            session_ts = msg[MessageBuilder.FIELD_TIME]
            addresses = self._server.get_registered_hosts()
            if self._master is None or self._master not in addresses or self._master == addr:
                # When starting a brand new session, the thread pool must be reset in order to prevent orphan tasks
                # from the previous session to keep running.
                # The only exception is when the session start command refers to a started session, that must be
                # restored after a disconnection of the master.
                if not self._server.reSendMsgs or self._session_timestamp != session_ts or self._master is None:
                    self._pool.stop(kill_abruptly=True)
                    self._pool.start()
                    err = -1
                # If there is no current master, or the previous one lost its connection, we accept the
                # session start request of the new host
                self._master = addr
                self._session_timestamp = session_ts
                ack = True
                InjectorEngine.logger.info('Injection session started with controller %s' % formatipport(addr))
            else:
                InjectorEngine.logger.info('Injection session rejected with controller %s' % formatipport(addr))
            # An ack (positive or negative) is sent to the sender host
        self._server.send_msg(addr, MessageBuilder.ack(time(), ack, err))

    def _signalhandler(self, sig, frame):
        """
        A signal handler to perform a graceful exit procedure on SIGINT 
        """
        if sig == signal.SIGINT or sig == signal.SIGTERM:
            InjectorEngine.logger.info('Exit requested by user. Cleaning up...')
            self._pool.stop(kill_abruptly=self._kill_abruptly)
            self._server.stop()
            self._subman.stop_subprocesses()
            InjectorEngine.logger.info('Injection engine stopped by user!')
            exit()
