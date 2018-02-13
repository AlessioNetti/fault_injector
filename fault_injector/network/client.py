import select, socket, logging
from fault_injector.network.msg_entity import MessageEntity
from fault_injector.network.msg_builder import MessageBuilder
from fault_injector.util.misc import strtoaddr, formatipport
from time import time


class Client(MessageEntity):
    """
    Class that implements a client which can communicate with multiple servers.
    
    """

    # Logger for the class
    logger = logging.getLogger(__name__)

    BROADCAST_RESTORED_ID = 'r*'

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
        # The list of hosts for which connection was successfully re-established
        self._restored = []
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

    def broadcast_to_restored_hosts(self, comm):
        """
        Public method for broadcasting messages

        This variant targets specifically hosts whose connection has been restored after one or more retries, and need
        a new handshake message

        :param comm: The message to be sent
        """
        if comm is None or not isinstance(comm, dict):
            MessageEntity.logger.error('Messages must be supplied as dictionaries to send_msg')
            return
        addr = (Client.BROADCAST_RESTORED_ID, Client.BROADCAST_RESTORED_ID)
        self._outputLock.acquire()
        self._outputQueue.append((addr, comm))
        self._outputLock.release()
        # Writing to the internal pipe to wake up the server if it is waiting on a select call
        self._dummy_sock_w.send(MessageEntity.DUMMY_STR)

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
                self._restore_dangling_connections()
            except socket.timeout:
                pass
            except select.error:
                self._trim_dead_sockets()
        for sock in self._registeredHosts.values():
            sock.close()
        Client.logger.info('Client has been shut down')

    def _flush_output_queue(self):
        """
        Private method that tries to dispatch all pending messages in the output queue
        """
        # Flushing the dummy socket used for triggering select calls
        self._dummy_sock_r.recv(2048)
        # The outbound message queue is flushed and transferred to a private list
        self._outputLock.acquire()
        private_msg_list = self._outputQueue
        self._outputQueue = []
        self._outputLock.release()
        for addr, msg in private_msg_list:
            if msg is not None:
                if addr[0] == MessageEntity.BROADCAST_ID:
                    to_remove = []
                    for re_addr in self._registeredHosts.keys():
                        if not self._send_msg(re_addr, msg):
                            to_remove.append(re_addr)
                    for re_addr in to_remove:
                        self._remove_host(re_addr)
                # This section tackles messages to be broadcasted at hosts whose connection was restored
                elif addr[0] == Client.BROADCAST_RESTORED_ID:
                    to_remove = []
                    for re_addr in self._restored:
                        if not self._send_msg(re_addr, msg):
                            to_remove.append(re_addr)
                    self._restored.clear()
                    for re_addr in to_remove:
                        self._remove_host(re_addr)
                else:
                    if not self._send_msg(addr, msg):
                        self._remove_host(addr)
            else:
                # Putting a None message on the queue means that the target host has to be removed
                self._remove_host(addr, now=True)
        private_msg_list.clear()

    def _remove_host(self, address, now=False):
        """
        Removes an host from the list of active hosts

        :param address: The (ip, port) address corresponding to the host to remove
        :param now: If True, the client will attempt to re-establish a connection with the target host
        """
        super(Client, self)._remove_host(address)
        self._add_to_input_queue(address, MessageBuilder.connection_status(time()))
        if not now and address not in self._dangling:
            first_time = time() - self._retry_period
            self._dangling[address] = [first_time, first_time]

    def _restore_dangling_connections(self):
        if len(self._dangling) > 0:
            time_now = time()
            for addr, time_list in self._dangling.items():
                if time_now - time_list[1] > self._retry_interval:
                    self._remove_host(addr, now=True)
                    self._dangling.pop(addr, None)
                elif time_now - time_list[0] >= self._retry_period:
                    time_list[0] = time_now
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.connect((socket.gethostbyname(addr[0]), addr[1]))
                        self._register_host(sock, overwrite=True)
                        self._dangling.pop(addr, None)
                        self._add_to_input_queue(addr, MessageBuilder.connection_status(time(), restored=True))
                        self._restored.append(addr)
                        Client.logger.info('Connection to server %s was successfully restored' % formatipport(addr))
                    except (ConnectionError, ConnectionRefusedError, TimeoutError, ConnectionAbortedError):
                        pass

    def get_n_restored_connections(self):
        return len(self._restored)
