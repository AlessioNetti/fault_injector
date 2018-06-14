"""
MIT License

Copyright (c) 2018 AlessioNetti

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import socket, threading
from fault_injector.network.msg_builder import MessageBuilder
from os.path import basename


ADDR_SEPARATOR = ':'

INJ_PREFIX = '/injection-'
OUT_PREFIX = '/output-'
LIST_PREFIX = '/listening-'

SUDO_ID = 'sudo'
SHELL_SCRIPT_EXT = '.sh'
EXEC_ID = './'
BASE_NUMA_COMMAND = 'numactl'
OPT_NUMA_COMMAND = '--physcpubind='
VALUE_ALL_CORES = 'all'
TASKNAME_SEPARATOR = '_'

VER_ID = '1.0'


def is_shell_script(argstring):
    """
    Given a string for a shell command, determines if the command is a shell script or not.

    :param argstring: A shell command
    :return: True if the command is a shell script, False otherwise
    """
    task_name = argstring.replace(SUDO_ID, '').replace(EXEC_ID, '')
    basename = task_name.strip().split(' ')[0]
    return basename.endswith(SHELL_SCRIPT_EXT)


def format_numa_command(arglist, cores):
    """
    Formats an ordinary command to be preceded by a NUMA policy command, specifying the cores on which to run.
    
    :param arglist: the list of arguments of the command
    :param cores: the string of cores to be included in the NUMA policy
    :return: the formatted arguments list
    """
    numalist = [BASE_NUMA_COMMAND, OPT_NUMA_COMMAND+cores]
    return numalist + arglist


def format_injection_filename(results_dir, addr, workload_name=None):
    """
    Returns a string used to name an execution record related to a specific fault injection session.

    If no workload name is specified, the file is flagged as a listening session,
    with the client operating in pull mode.

    :param results_dir: Target directory of the file
    :param addr: (ip, port) tuple representing the address of the target host
    :param workload_name: Name of the injected workload
    :return: A string, representing the name of the execution record file
    """
    if workload_name is not None:
        return results_dir + INJ_PREFIX + workload_name + '-' + addr[0] + '_' + str(addr[1]) + '.csv'
    else:
        return results_dir + LIST_PREFIX + addr[0] + '_' + str(addr[1]) + '.csv'


def format_output_filename(results_dir, msg):
    """
    Returns a string used to name the output of a specific task.

    :param results_dir: The target directory of the file
    :param msg: The dictionary containing all info regarding the task
    :return: A string representing the path of the file
    """
    return results_dir + OUT_PREFIX + format_task_filename(msg) + '.log'


def format_output_directory(results_dir, addr, workload_name=None):
    """
    Returns a string used to name the output log directory, containing all logs related to tasks executed in
    an injection session.

    :param results_dir: The target directory of the file
    :param addr: The address of the host on which the workload was injected
    :param workload_name: The name of the workload
    :return: A string used to name the output log directory
    """
    if workload_name is not None:
        return results_dir + OUT_PREFIX + workload_name + '-' + addr[0] + '_' + str(addr[1])
    else:
        return results_dir + OUT_PREFIX + addr[0] + '_' + str(addr[1])


def format_task_filename(msg):
    """
    Given a task end message, this method returns the associated name for the command line output log file

    :param msg: A message dictionary
    :return: A string representing the filename of the output log for the task
    """
    task_name = msg[MessageBuilder.FIELD_DATA].replace(SUDO_ID, '').replace(EXEC_ID, '')
    return basename(task_name.strip().split(' ')[0]) + TASKNAME_SEPARATOR + str(msg[MessageBuilder.FIELD_SEQNUM])


def format_task_filename_cores(msg):
    """
    Given a task end message, this method returns the associated name for the command line output log file, with the
    associated cores list (if present)

    :param msg: A message dictionary
    :return: A string representing the filename of the output log for the task
    """
    task_name = msg[MessageBuilder.FIELD_DATA].replace(SUDO_ID, '').replace(EXEC_ID, '')
    cores = msg[MessageBuilder.FIELD_CORES]
    if cores is not None:
        return basename(task_name.strip().split(' ')[0]) + TASKNAME_SEPARATOR + cores
    else:
        return basename(task_name.strip().split(' ')[0])


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
        try:
            addr[1] = int(addr[1])
        except ValueError:
            return None
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
