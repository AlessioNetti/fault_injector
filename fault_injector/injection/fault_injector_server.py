import logging, signal
from time import time
from fault_injector.network.server import Server
from fault_injector.injection.thread_pool import InjectionThreadPool
from fault_injector.network.msg_builder import MessageBuilder
from fault_injector.util.misc import formatipport
from fault_injector.util.config_tools import ConfigLoader
from fault_injector.io.task import Task

class InjectorServer:
    """
    This class manages the entire fault injection process, by executing tasks and communicating their outcome
    """

    # Logger for the class
    logger = logging.getLogger(__name__)

    @staticmethod
    def build(config=None):
        """
        Static method that automatically builds an InjectorServer object starting from a given configuration file
        
        :param config: The path to the json configuration file
        :return: An InjectionServer object
        """
        cfg = ConfigLoader.getConfig(config)
        se = Server(port=cfg['SERVER_PORT'], socket_timeout=cfg['SOCKET_TIMEOUT'], max_connections=cfg['MAX_CONNECTIONS'])
        inj_s = InjectorServer(serverobj=se, max_requests=cfg['MAX_REQUESTS'], skip_expired=cfg['SKIP_EXPIRED'],
                               retry_tasks=cfg['RETRY_TASKS'], kill_abruptly=cfg['ABRUPT_TASK_KILL'])
        return inj_s

    def __init__(self, serverobj, max_requests=20, skip_expired=True, retry_tasks=True, kill_abruptly=True):
        """
        Constructor for the class
        
        :param serverobj: Server object to be used for communication
        :param max_requests: Number of maximum concurrent task requests. See InjectionThreadPool for details
        :param skip_expired: Boolean flag. See InjectionThreadPool for details
        :param retry_tasks: Boolean flag. See InjectionThreadPool for details
        :param kill_abruptly: Boolean flag. See InjectionThreadPool for details
        """
        assert isinstance(serverobj, Server), 'InjectorServer needs a Server object in its constructor!'
        self._server = serverobj
        self._master = None
        self._kill_abruptly = kill_abruptly
        self._pool = InjectionThreadPool(msg_server=self._server, max_requests=max_requests, skip_expired=skip_expired,
                                         retry_tasks=retry_tasks)

    def listen(self):
        """
        Listens for incoming fault injection requests and executes them 
        """
        signal.signal(signal.SIGINT, self._signalhandler)
        self._server.start()
        self._pool.start()
        while True:
            # Waiting for a new requests to arrive
            addr, msg = self._server.pop_msg_queue()
            msg_type = msg[MessageBuilder.FIELD_TYPE]
            # If a session command has arrived, we process it accordingly
            if msg_type == MessageBuilder.COMMAND_START_SESSION or msg_type == MessageBuilder.COMMAND_END_SESSION:
                self._update_session(addr, msg)
            # Processing a termination command
            elif msg_type == MessageBuilder.COMMAND_TERMINATE:
                self._check_for_termination(addr, msg)
            # If a new command has been issued by the current session master, we add it to the thread pool queue
            elif addr == self._master and msg[MessageBuilder.FIELD_TYPE] == MessageBuilder.COMMAND_START:
                self._pool.submit_task(Task.msg_to_task(msg))
            else:
                InjectorServer.logger.warning('Invalid command sent from non-master host %s', formatipport(addr))

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
        timestamp = time()
        if msg[MessageBuilder.FIELD_TYPE] == MessageBuilder.COMMAND_END_SESSION and addr == self._master:
            # If the current master has terminated its session, we react accordingly
            self._master = None
            ack = True
            InjectorServer.logger.info('Injection session terminated with client %s' % formatipport(addr))
        elif msg[MessageBuilder.FIELD_TYPE] == MessageBuilder.COMMAND_START_SESSION:
            addresses = self._server.get_registered_hosts().keys()
            if self._master is None or self._master not in addresses:
                # If there is no current master, or the previous one lost its connection, we accept the session
                # start request of the new host
                self._master = addr
                ack = True
                # The session start command is also used to set the timestamp at which the 'workload' is started
                self._pool.reset_session(msg[MessageBuilder.FIELD_TIME], timestamp)
                InjectorServer.logger.info('Injection session started with client %s' % formatipport(addr))
            else:
                InjectorServer.logger.info('Injection session rejected with client %s' % formatipport(addr))
            # An ack (positive or negative) is sent to the sender host
        self._server.send_msg(addr, MessageBuilder.ack(timestamp, ack))

    def _signalhandler(self, sig, frame):
        """
        A signal handler to perform a graceful exit procedure on SIGINT 
        """
        if sig == signal.SIGINT:
            InjectorServer.logger.info('Exit requested by user. Cleaning up...')
            self._pool.stop(kill_abruptly=self._kill_abruptly)
            self._server.stop()
            InjectorServer.logger.info('Injection server stopped by user!')
            exit()
