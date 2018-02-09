import select, socket, logging
from fault_injector.network.msg_entity import MessageEntity
from fault_injector.util.misc import strtoaddr


class Client(MessageEntity):
    """
    Class that implements a client which can communicate with multiple servers.
    
    """

    logger = logging.getLogger(__name__)

    def __init__(self, socket_timeout=10):
        """
        Constructor for the class
        
        :param socket_timeout: timeout for the sockets
        """
        super().__init__(socket_timeout)
        self._readSet = [self._dummy_sock_r]

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
            except socket.timeout:
                pass
            except select.error:
                self._trim_dead_sockets()
        for sock in self._registeredHosts.values():
            sock.close()
        Client.logger.info('Client has been shut down')

