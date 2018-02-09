import socket, threading

ADDR_SEPARATOR = ':'

def getipport(sock):
    """
    Returns a ip:port string corresponding to the address of the input socket
    """
    name = sock.getpeername()
    return ADDR_SEPARATOR.join([name[0], str(name[1])])


def formatipport(addr):
    """
    Formats the (ip, port) input tuple to a ip:port string
    """
    ip = addr[0]
    port = str(addr[1])
    return ADDR_SEPARATOR.join([ip, port])

def strtoaddr(s):
    """
    Converts a ip:port string to its tuple (ip, port) equivalent
    """
    addr = [a.strip() for a in s.split(ADDR_SEPARATOR)]
    if len(addr) == 2:
        addr[1] = int(addr[1])
        return addr
    else:
        return None


class DummySocketBuilder:
    """
    Class that returns a dummy socket that works like a pipe: one descriptor is used for reading, another for writing.
    This is useful to awake servers waiting on select calls.
    """

    _localhost_id = ''
    _read_socket = None
    _write_socket = None

    @staticmethod
    def getDummySocket():
        serverAddress = (DummySocketBuilder._localhost_id, 0)
        serverSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serverSock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        serverSock.bind(serverAddress)
        serverSock.listen(1)
        port = serverSock.getsockname()[1]
        t = threading.Thread(target=DummySocketBuilder._selfconnect, args=[port])
        t.start()
        connection, client_address = serverSock.accept()
        DummySocketBuilder._read_socket = connection
        t.join()
        serverSock.close()
        DummySocketBuilder._read_socket.setblocking(False)
        DummySocketBuilder._write_socket.setblocking(False)
        return DummySocketBuilder._read_socket, DummySocketBuilder._write_socket

    @staticmethod
    def _selfconnect(port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((DummySocketBuilder._localhost_id, port))
        DummySocketBuilder._write_socket = sock
