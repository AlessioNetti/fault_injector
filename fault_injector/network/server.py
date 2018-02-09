import select, socket, logging
from fault_injector.network.msg_entity import MessageEntity
from fault_injector.util.misc import getipport


class Server(MessageEntity):
    """
    Class that implements a simple server enabled for communication with multiple clients.
    
    """

    logger = logging.getLogger(__name__)

    def __init__(self, port, socket_timeout=10, max_connections=100):
        """
        Constructor for the class
        
        :param port: Listening port for the server socket
        :param socket_timeout: Timeout for the sockets
        :param max_connections: Maximum number of concurrent connections to the server
        """
        super().__init__(socket_timeout, max_connections)
        # The server socket must be initialized
        self._serverAddress = ('', port)
        af = socket.AF_INET
        self._serverSock = socket.socket(af, socket.SOCK_STREAM)
        self._serverSock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._readSet = [self._dummy_sock_r, self._serverSock]

    def _listen(self):
        """
        Method that implements the basic listener behavior of the server
        
        No action is taken upon the reception of a message: it is up to the user to decide how to react by looking
        at the message queue and taking action
        """
        # Listen for incoming connections
        self._serverSock.bind(self._serverAddress)
        self._serverSock.listen(self._max_connections)
        Server.logger.info('Server has been started')
        while not self._hasToFinish:
            try:
                read, wr, err = select.select(self._readSet, [], self._readSet, self._sock_timeout)
                for sock in err:
                    self._remove_host(sock.getpeername())
                    if sock in read:
                        read.remove(sock)
                for sock in read:
                    if sock == self._serverSock:
                        connection, client_address = self._serverSock.accept()
                        self._register_host(connection)
                        Server.logger.info('Client %s has subscribed' % getipport(connection))
                    elif sock == self._dummy_sock_r:
                        self._flush_output_queue()
                    else:
                        if not self._liveness_check(sock):
                            self._remove_host(sock.getpeername())
                        else:
                            data = self._recv_msg(sock)
                            if data:
                                self._add_to_input_queue(sock.getpeername(), data)
            except socket.timeout:
                pass
            except select.error:
                self._trim_dead_sockets()
        self._serverSock.close()
        self._dummy_sock_r.close()
        self._dummy_sock_w.close()
        for sock in self._registeredHosts.values():
            sock.close()
        Server.logger.info('Server has been shut down')

    def _update_read_set(self):
        """
        Updates the list of socket enabled for reading on the 'select' calls
        """
        self._readSet = [self._serverSock, self._dummy_sock_r] + list(self._registeredHosts.values())
