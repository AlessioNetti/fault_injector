import select, socket, logging
from fault_injector.network.msg_entity import MessageEntity
from fault_injector.util.misc import getipport


class MessageServer(MessageEntity):
    """
    Class that implements a simple server enabled for communication with multiple clients.
    
    """

    logger = logging.getLogger('MessageServer')

    def __init__(self, port, socket_timeout=10, max_connections=100, re_send_msgs=False):
        """
        Constructor for the class
        
        :param port: Listening port for the server socket
        :param socket_timeout: Timeout for the sockets
        :param max_connections: Maximum number of concurrent connections to the server
        :param re_send_msgs: if True, the entity will keep track of sent/received messages, and eventually attempt
            to resend them to hosts that have not received them due to a connection loss
        """
        assert port is not None, 'A listening port for the server must be specified'
        super().__init__(socket_timeout=socket_timeout, max_connections=max_connections, re_send_msgs=re_send_msgs)
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
        self._serverSock.listen(self.max_connections)
        MessageServer.logger.info('Server has been started')
        while not self._hasToFinish:
            try:
                read, wr, err = select.select(self._readSet, [], self._readSet, self.sock_timeout)
                for sock in err:
                    self._remove_host(sock.getpeername())
                    if sock in read:
                        read.remove(sock)
                for sock in read:
                    if sock == self._serverSock:
                        connection, client_address = self._serverSock.accept()
                        self._register_host(connection)
                        MessageServer.logger.info('Client %s has subscribed' % getipport(connection))
                    elif sock == self._dummy_sock_r:
                        self._flush_output_queue()
                    else:
                        if not self._liveness_check(sock):
                            self._remove_host(sock.getpeername())
                        else:
                            peername = sock.getpeername()
                            data, seq_num = self._recv_msg(sock)
                            if data is not None:
                                self._add_to_input_queue(peername, data)
                            elif self.reSendMsgs and seq_num is not None:
                                self._forward_old_msgs(seq_num, peername)

            except socket.timeout:
                pass
            except select.error:
                self._trim_dead_sockets()
        self._serverSock.close()
        self._dummy_sock_r.close()
        self._dummy_sock_w.close()
        for sock in self._registeredHosts.values():
            sock.close()
        MessageServer.logger.info('Server has been shut down')

    def _update_seq_num(self, addr, seq_num, received=True):
        """
        Refreshes the sequence number associated to a certain connected host
        
        This implementation of the method is a dummy and does nothing. This is because in our client-server architecture
        it is the client that tracks the sequence numbers of received/sent messages, and that has priority in the
        message forwarding process

        :param addr: The address of the connected host
        :param seq_num: The sequence number associated to the connected host, in tuple format
        :param received: If True, then the sequence number refers to a received message, and sent otherwise
        """
        pass

    def _update_read_set(self):
        """
        Updates the list of socket enabled for reading on the 'select' calls
        """
        self._readSet = [self._serverSock, self._dummy_sock_r] + list(self._registeredHosts.values())
