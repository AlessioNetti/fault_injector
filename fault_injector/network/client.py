import select, socket, logging
from fault_injector.network.msg_entity import MessageEntity
from fault_injector.util.misc import formatipport
from time import time


class Client(MessageEntity):
    """
    Class that implements a client which can communicate with multiple servers.
    
    """

    # Logger for the class
    logger = logging.getLogger(__name__)

    def __init__(self, socket_timeout=10, retry_interval=600, retry_period=30, re_send_msgs=False):
        """
        Constructor for the class
        
        :param socket_timeout: timeout for the sockets
        :param retry_interval: the total span of time in which to retry connections with failed hosts
        :param retry_period: the period of single connection retries
        :param re_send_msgs: if True, the entity will keep track of sent/received messages, and eventually attempt
            to resend them to hosts that have not received them due to a connection loss
        """
        super().__init__(socket_timeout=socket_timeout, re_send_msgs=re_send_msgs)
        self._readSet = [self._dummy_sock_r]
        # Dictionary of hosts for which we are trying to re-establish connection, with (ip, port) keys
        self._dangling = {}
        # Dictionary of last (received, sent) tuples for sequence numbers from connected hosts
        self._seq_nums = {}
        self.retry_interval = retry_interval
        self.retry_period = retry_period

    def add_servers(self, addrs):
        """
        Method that opens connection with a specified list of ips/ports of servers
        
        :param addrs: The addresses of servers to which to connect, in (ip, port) tuple format
        """
        if addrs is None:
            Client.logger.error('You must specify one or more addresses to start the client')
            return
        if not isinstance(addrs, (list, tuple)):
            addrs = [addrs]
        for addr in addrs:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((socket.gethostbyname(addr[0]), addr[1]))
                self._register_host(sock)
                Client.logger.info('Successfully connected to server %s' % formatipport(addr))
            except (ConnectionError, ConnectionRefusedError, TimeoutError, ConnectionAbortedError, socket.gaierror):
                Client.logger.warning('Could not connect to %s' % formatipport(addr))
                pass

    def _listen(self):
        """
        Listener method that processes messages received by the client
        
        No action is taken upon the reception of a message: it is up to the user to decide how to react by looking
        at the message queue and taking action
        """
        Client.logger.info('Client has been started')
        while not self._hasToFinish:
            try:
                read, wr, err = select.select(self._readSet, [], self._readSet, self.sock_timeout)
                for sock in err:
                    # All of the sockets reported in error state by select must be removed
                    self._remove_host(sock.getpeername())
                for sock in read:
                    if sock == self._dummy_sock_r:
                        self._flush_output_queue()
                    elif not self._liveness_check(sock):
                        self._remove_host(sock.getpeername())
                    else:
                        data, seq_num = self._recv_msg(sock)
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

    def _update_seq_num(self, addr, seq_num, received=True):
        """
        Refreshes the sequence number associated to a certain connected host

        :param addr: The address of the connected host
        :param seq_num: The sequence number associated to the connected host
        :param received: If True, then the sequence number refers to a received message, and sent otherwise
        """
        if addr not in self._seq_nums:
            self._seq_nums[addr] = [seq_num, None] if received else [None, seq_num]
            return
        # We do not check for the value of the new sequence number. This can be done because, since we are using TCP,
        # we expect data to arrive in the same order as it was originally sent, thus resulting in increasing seq nums
        if received:
            self._seq_nums[addr][0] = seq_num
        else:
            self._seq_nums[addr][1] = seq_num

    def _remove_host(self, address, now=False):
        """
        Removes an host from the list of active hosts

        :param address: The (ip, port) address corresponding to the host to remove
        :param now: If False, the client will attempt to re-establish a connection with the target host
        """
        super(Client, self)._remove_host(address)
        # When connection is lost, we inject a status message for that host in the input queue
        self._add_to_input_queue(address, MessageEntity.CONNECTION_LOST_MSG)
        if not now and address not in self._dangling:
            first_time = time() - self.retry_period
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
                if time_now - time_list[1] > self.retry_interval:
                    self._add_to_input_queue(addr, MessageEntity.CONNECTION_FINALIZED_MSG)
                    to_pop.append(addr)
                # We retry establishing a connection with the dangling host
                elif time_now - time_list[0] >= self.retry_period:
                    time_list[0] = time_now
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.connect((socket.gethostbyname(addr[0]), addr[1]))
                        self._register_host(sock, overwrite=True)
                        if self.reSendMsgs:
                            self._forward_old_msgs(self._seq_nums[addr][1], addr)
                            self._send_msg(self._seq_nums[addr][0], addr, None)
                        to_pop.append(addr)
                        # When connection is re-established, we inject a status message for that host in the input queue
                        self._add_to_input_queue(addr, MessageEntity.CONNECTION_RESTORED_MSG)
                        Client.logger.info('Connection to server %s was successfully restored' % formatipport(addr))
                    except (ConnectionError, ConnectionRefusedError, TimeoutError, ConnectionAbortedError):
                        pass
            # We remove all hosts for which connection was re-established from the dangling ones
            for addr in to_pop:
                self._dangling.pop(addr, None)
            to_pop.clear()


