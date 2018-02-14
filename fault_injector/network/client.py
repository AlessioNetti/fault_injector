import select, socket, logging
from fault_injector.network.msg_entity import MessageEntity
from fault_injector.util.misc import strtoaddr, formatipport
from time import time


class Client(MessageEntity):
    """
    Class that implements a client which can communicate with multiple servers.
    
    """

    # Logger for the class
    logger = logging.getLogger(__name__)

    # Static definitions for messages regarding the status of a connection
    _CONNECTION_LOST_MSG = False
    _CONNECTION_RESTORED_MSG = True

    @staticmethod
    def is_status_message(msg):
        """
        Inspects the type of a message received on the queue, and determines if it is a status message

        When connections are lost or restored, status messages are injected into the input queue in order to
        asynchronously signal the status change. This method allows to determine if a message in the queue is of
        such type.

        :param msg: The message to be inspected
        :return: A tuple of bools: the first element is True if msg is a status message, and the second expresses the
            status change of the connection (True if restored, False if lost)
        """
        if isinstance(msg, type(Client._CONNECTION_RESTORED_MSG)):
            return True, msg == Client._CONNECTION_RESTORED_MSG
        else:
            return False, None

    def __init__(self, socket_timeout=10, retry_interval=600, retry_period=30):
        """
        Constructor for the class
        
        :param socket_timeout: timeout for the sockets
        :param retry_interval: the total span of time in which to retry connections with failed hosts
        :param retry_period: the period of single connection retries
        """
        super().__init__(socket_timeout)
        self._readSet = [self._dummy_sock_r]
        # Dictionary of hosts for which we are trying to re-establish connection, with (ip, port) keys
        self._dangling = {}
        self._retry_interval = retry_interval
        self._retry_period = retry_period

    def add_servers(self, addrs):
        """
        Method that opens connection with a specified list of ips/ports of servers
        
        :param addrs: The addresses of servers to which to connect, in "ip:port" string format
        """
        if not isinstance(addrs, (list, tuple)):
            addrs = [addrs]
        for str_addr in addrs:
                addr = strtoaddr(str_addr)
                if addr is not None:
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.connect((socket.gethostbyname(addr[0]), addr[1]))
                        self._register_host(sock)
                        Client.logger.info('Successfully connected to server %s' % str_addr)
                    except (ConnectionError, ConnectionRefusedError, TimeoutError, ConnectionAbortedError):
                        Client.logger.warning('Could not connect to %s' % str_addr)
                        pass
                else:
                    Client.logger.error('Address %s is malformed' % str_addr)

    def _listen(self):
        """
        Listener method that processes messages received by the client
        
        No action is taken upon the reception of a message: it is up to the user to decide how to react by looking
        at the message queue and taking action
        """
        Client.logger.info('Client has been started')
        while not self._hasToFinish:
            try:
                read, wr, err = select.select(self._readSet, [], self._readSet, self._sock_timeout)
                for sock in err:
                    # All of the sockets reported in error state by select must be removed
                    self._remove_host(sock.getpeername())
                for sock in read:
                    if sock == self._dummy_sock_r:
                        self._flush_output_queue()
                    elif not self._liveness_check(sock):
                        self._remove_host(sock.getpeername())
                    else:
                        data = self._recv_msg(sock)
                        if data:
                            self._add_to_input_queue(sock.getpeername(), data)
                # We try to re-establish connection with lost hosts, if present
                self._restore_dangling_connections()
            except socket.timeout:
                pass
            except select.error:
                self._trim_dead_sockets()
        for sock in self._registeredHosts.values():
            sock.close()
        Client.logger.info('Client has been shut down')

    def _remove_host(self, address, now=False):
        """
        Removes an host from the list of active hosts

        :param address: The (ip, port) address corresponding to the host to remove
        :param now: If False, the client will attempt to re-establish a connection with the target host
        """
        super(Client, self)._remove_host(address)
        # When connection is lost, we inject a status message for that host in the input queue
        self._add_to_input_queue(address, Client._CONNECTION_LOST_MSG)
        if not now and address not in self._dangling:
            first_time = time() - self._retry_period
            # This list contains two items: the timestamp of when connection was lost, and the timestamp of the last
            # re-connection attempt
            self._dangling[address] = [first_time, first_time]

    def _restore_dangling_connections(self):
        """
        Tries to re-establish connection with "dangling" hosts

        A "dangling" host is one whose connection has been recently lost, in a time window that falls within
        retry_interval. If the connection could not be established by the end of the time window, the host is dropped
        """
        if len(self._dangling) > 0:
            time_now = time()
            to_pop = []
            for addr, time_list in self._dangling.items():
                # If a dangling host has passed its retry interval, we remove it completely
                if time_now - time_list[1] > self._retry_interval:
                    to_pop.append(addr)
                # We retry establishing a connection with the dangling host
                elif time_now - time_list[0] >= self._retry_period:
                    time_list[0] = time_now
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.connect((socket.gethostbyname(addr[0]), addr[1]))
                        self._register_host(sock, overwrite=True)
                        to_pop.append(addr)
                        # When connection is re-established, we inject a status message for that host in the input queue
                        self._add_to_input_queue(addr, Client._CONNECTION_RESTORED_MSG)
                        Client.logger.info('Connection to server %s was successfully restored' % formatipport(addr))
                    except (ConnectionError, ConnectionRefusedError, TimeoutError, ConnectionAbortedError):
                        pass
            # We remove all hosts for which connection was re-established from the dangling ones
            for addr in to_pop:
                self._dangling.pop(addr, None)
            to_pop.clear()
