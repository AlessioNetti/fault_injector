import select, socket, threading
import struct, json, logging
from fault_injector.util.misc import getipport, formatipport, DummySocketBuilder
from threading import Semaphore
from collections import deque
from abc import ABC, abstractmethod


class MessageEntity(ABC):
    """
    Abstract class that supplies a basic message-based communication protocol based on TCP sockets.
    
    This class supports one-to-many communication with broadcast capabilities, and implements a message queue.
    Messages must be supplied as dictionaries of arbitrary length, which will be converted to json.
    Users must implement the 'listen' abstract method, in which the behavior of the listener is implemented. This
    is relevant depending on the nature of the communication entity (client or server).
    """

    # Logger for the class
    logger = logging.getLogger(__name__)

    # ID used to identify outbound broadcast messages
    BROADCAST_ID = '*'
    DUMMY_STR = b'-'

    def __init__(self, socket_timeout=10, max_connections=100):
        """
        Constructor of the class
        
        :param socket_timeout: timeout for the underlying sockets
        :param max_connections: maximum number of concurrent connections (used for servers only)
        """
        # The thread object for the listener and a termination flag
        self._thread = None
        self._initialized = False
        self._hasToFinish = False
        # Timeout to be used for the sockets
        self._sock_timeout = socket_timeout
        # Maximum number of requests for server sockets
        self._max_connections = max_connections
        # The dictionary of sockets registered for communication, whether server or client
        # The keys are in the form of (ip, port) tuples
        self._registeredHosts = {}
        # The list of hosts registered for the 'select' calls (also includes the server socket, if present)
        self._readSet = []
        # Input and output message queues
        self._inputQueue = deque()
        self._outputQueue = deque()
        # This socket is used to wake up the messaging thread when there are outbound messages to be sent
        reads, writes = DummySocketBuilder.getDummySocket()
        self._dummy_sock_r = reads
        self._dummy_sock_w = writes
        # Semaphore for producer-consumer style computation on the message queue
        self._messageSem = Semaphore(0)

    def start(self):
        """
        Method that starts the listener thread
        """
        if not self._initialized:
            self._thread = threading.Thread(target=self._listen)
            self._initialized = True
            self._hasToFinish = False
            self._thread.start()
            MessageEntity.logger.debug('Messaging thread successfully started')
        else:
            MessageEntity.logger.warning('Cannot start messaging thread if it is already running')

    def stop(self):
        """
        Method that terminates the listener thread
        """
        if self._initialized:
            self._hasToFinish = True
            self._thread.join()
            self._thread = None
            self._initialized = False
            MessageEntity.logger.debug('Messaging thread successfully stopped')

    def get_registered_hosts(self):
        """
        Returns a list of (ip, port) addresses with which communication is currently active

        """
        return list(self._registeredHosts.keys())

    def get_n_registered_hosts(self):
        """
        Returns the number of currently connected hosts

        :return: the number of currently connected hosts
        """
        return len(self._registeredHosts)

    def send_msg(self, addr, comm):
        """
        Public method for sending messages, that uses address (ip, port) tuples to identify an host
        
        :param addr: the address (ip, port) tuple of the target host
        :param comm: The message to be sent
        """
        if comm is None or not isinstance(comm, dict):
            MessageEntity.logger.error('Messages must be supplied as dictionaries to send_msg')
            return
        self._outputQueue.append((addr, comm))
        # Writing to the internal socket to wake up the server if it is waiting on a select call
        self._dummy_sock_w.send(MessageEntity.DUMMY_STR)

    def broadcast_msg(self, comm):
        """
        Public method for broadcasting messages

        :param comm: The message to be sent
        """
        if comm is None or not isinstance(comm, dict):
            MessageEntity.logger.error('Messages must be supplied as dictionaries to send_msg')
            return
        addr = (MessageEntity.BROADCAST_ID, MessageEntity.BROADCAST_ID)
        self._outputQueue.append((addr, comm))
        # Writing to the internal pipe to wake up the server if it is waiting on a select call
        self._dummy_sock_w.send(MessageEntity.DUMMY_STR)

    def peek_msg_queue(self):
        """
        Returns the length of the message queue

        :return: The length of the message queue
        """
        return len(self._inputQueue)

    def pop_msg_queue(self, blocking=True):
        """
        Pops the first element of the message queue

        :param blocking: boolean flag. If True, the method is blocking, and the process is halted until a new message 
            has been received (if the queue is empty)
        :return: The first message in the queue
        """
        self._messageSem.acquire(blocking)
        addr, comm = self._inputQueue.popleft() if len(self._inputQueue) > 0 else (None, None)
        return addr, comm

    def remove_host(self, addr):
        """
        Removes an host from the list of active hosts

        Public, asynchronous version of the private method

        :param addr: The (ip, port) address corresponding to the host to remove
        """
        self._outputQueue.append((addr, None))

    def _send_msg(self, addr, comm):
        """
        Private method that sends messages over specific active hosts of the registered hosts list

        :param addr: address of the target host
        :param comm: content of the message. Must be supplied as a dictionary
        :return: True if the message was successfully sent, False otherwise
        """
        # Verifying if the input address has a corresponding open socket
        try:
            sock = self._registeredHosts[addr]
        except KeyError:
            sock = None
        # If no valid socket was found for the input address, the message is not sent
        if sock is None:
            MessageEntity.logger.error('Cannot send to %s, is not registered' % formatipport(addr))
            return False
        msg = json.dumps(comm).encode()
        # Prefix each message with a 4-byte length (network byte order)
        msg = struct.pack('>I', len(msg)) + msg
        try:
            sock.sendall(msg)
            return True
        except Exception:
            MessageEntity.logger.error('Exception encountered while sending msg to %s' % getipport(sock))
            # If an error is encountered during communication, we suppose the host is dead
            return False

    def _flush_output_queue(self):
        """
        Private method that tries to dispatch all pending messages in the output queue
        """
        # Flushing the dummy socket used for triggering select calls
        self._dummy_sock_r.recv(2048)
        # We compute the number of messages currently in the output queue
        n_msg = len(self._outputQueue)
        for i in range(n_msg):
            addr, msg = self._outputQueue.popleft()
            if msg is not None:
                if addr[0] == MessageEntity.BROADCAST_ID:
                    to_remove = []
                    for re_addr in self._registeredHosts.keys():
                        if not self._send_msg(re_addr, msg):
                            to_remove.append(re_addr)
                    for re_addr in to_remove:
                        self._remove_host(re_addr)
                else:
                    if not self._send_msg(addr, msg):
                        self._remove_host(addr)
            else:
                # Putting a None message on the queue means that the target host has to be removed
                self._remove_host(addr)

    def _add_to_input_queue(self, addr, comm):
        """
        Adds a message that has been received to the internal message queue

        :param addr: The address (ip, port) of the sender host
        :param comm: The message to be added to the queue
        """
        self._inputQueue.append((addr, comm))
        self._messageSem.release()

    def _liveness_check(self, sock):
        """
        Checks for the liveness of a socket by trying to read 1 byte (with MSG_PEEK). This supposes that the socket has
        been flagged as readable by a previous 'select' call

        :param sock: the socket to be checked
        :return: True if the socket is alive, False otherwise
        """
        try:
            if len(sock.recv(1, socket.MSG_PEEK)) == 0:
                MessageEntity.logger.info('Host %s has disconnected' % getipport(sock))
                return False
            else:
                return True
        except Exception:
            MessageEntity.logger.info('Host %s has encountered an error' % getipport(sock))
            return False

    def _recv_msg(self, sock):
        """
        Performs the reception of a message from a given socket. This supposes that the socket has been already flagged
        as readable by a previous 'select' call

        :param sock: the socket from which the message must be read
        :return: The message dictionary, if successful, None otherwise
        """
        # Read message length and unpack it into an integer
        raw_msglen = self._recvall(sock, 4)
        if not raw_msglen:
            MessageEntity.logger.error('Empty message on recv_msg from %s' % getipport(sock))
            return None
        msglen = struct.unpack('>I', raw_msglen)[0]
        # Read the message data
        raw_msg = self._recvall(sock, msglen)
        return json.loads(raw_msg.decode()) if raw_msg else None

    def _recvall(self, sock, n):
        """
        Method that performs a series of reads on a socket in order to reach the (known) length of a received package

        The length of the message is always known since it is a part of the header in our protocol.

        :param sock: The socket from which the message must be received
        :param n: The length of the message
        """
        # Helper function to recv n bytes or return None if EOF is hit
        data = b''
        while len(data) < n:
            packet = sock.recv(n - len(data))
            if not packet:
                return None
            data += packet
        return data

    def _register_host(self, connection, overwrite=False):
        """
        Adds an host for which connection was successfully established to the list of active hosts

        :param connection: the socket object corresponding to the host
        :param overwrite: if True, connections will be overwritten by new connections to the same host
        """
        addr = connection.getpeername()
        if addr not in self._registeredHosts or overwrite:
            self._registeredHosts[addr] = connection
            self._update_read_set()
        else:
            connection.close()
            MessageEntity.logger.error('Cannot register host %s, is already registered' % formatipport(addr))

    def _remove_host(self, address):
        """
        Removes an host from the list of active hosts

        :param address: The (ip, port) address corresponding to the host to remove
        """
        if address in self._registeredHosts:
            self._registeredHosts[address].close()
            self._registeredHosts.pop(address, None)
            self._update_read_set()
        else:
            MessageEntity.logger.error('Cannot remove host %s, does not exist' % formatipport(address))

    def _trim_dead_sockets(self):
        """
        This method removes all sockets that are in error state from the list of active hosts

        Must be called every time a 'select' call fails.
        """
        for sock in self._registeredHosts.values():
            try:
                # We perform one select call on each active socket, and if an error is encountered,
                # the host is removed
                select.select([sock], [], [], 0)
            except select.error:
                MessageEntity.logger.warning('Removing host %s due to errors' % getipport(sock))
                self._remove_host(sock)

    def _update_read_set(self):
        """
        Updates the list of socket enabled for reading on the 'select' calls
        """
        self._readSet = [self._dummy_sock_r] + list(self._registeredHosts.values())

    @abstractmethod
    def _listen(self):
        """
        The listener method that is run by the thread for this class. Must implement the actual communication behavior
        (client, server, or other) of subclasses.
        """
        raise NotImplementedError('This method must be implemented')
