import logging, signal
from fault_injector.network.client import Client
from fault_injector.network.msg_builder import MessageBuilder
from fault_injector.util.config_tools import ConfigLoader
from fault_injector.util.misc import formatipport
from fault_injector.io.writer import ExecutionLogWriter
from os.path import splitext, basename
from time import sleep, time


class InjectorClient:

    logger = logging.getLogger(__name__)

    def __init__(self, clientobj, workload_padding=20, pre_send_interval=300, results_dir='results'):
        assert isinstance(clientobj, Client), 'InjectorClient needs a Client object in its constructor!'
        self._client = clientobj
        self._workloadPadding = workload_padding
        self._preSendInterval = pre_send_interval
        self._resultsDir = results_dir
        self._sleepPeriod = 1
        self._writer = None
        signal.signal(signal.SIGINT, self._signalhandler)

    @staticmethod
    def build(config=None, hosts=None):
        cfg = ConfigLoader.getConfig(config)
        cl = Client(socket_timeout=cfg['SOCKET_TIMEOUT'])
        inj_c = InjectorClient(clientobj=cl, workload_padding=cfg['WORKLOAD_PADDING'],
                               pre_send_interval=cfg['PRE_SEND_INTERVAL'], results_dir=cfg['RESULTS_DIR'])
        if hosts is None and 'HOSTS' in cfg:
            hosts = cfg['HOSTS']
        if hosts is not None:
            if not isinstance(hosts, (list, tuple)):
                hosts = list(hosts)
            cl.add_servers(hosts)
        return inj_c

    def stop(self):
        self._client.stop()

    def inject(self, reader):
        task = reader.read_entry()
        if task is None:
            InjectorClient.logger.warning("Input workload appears to be empty. Aborting injection...")
            return
        start_timestamp = task.timestamp - self._workloadPadding
        start_timestamp_abs = time()
        self._client.start()
        msg = MessageBuilder.command_session(start_timestamp)
        self._client.broadcast_msg(msg)
        addr, msg = self._client.pop_msg_queue()
        if msg[MessageBuilder.FIELD_TYPE] == MessageBuilder.ACK_YES:
            InjectorClient.logger.info("Injection session started with host %s" % formatipport(addr))
        elif msg[MessageBuilder.FIELD_TYPE] == MessageBuilder.ACK_NO:
            InjectorClient.logger.warning("Injection session request rejected by host %s" % formatipport(addr))
            return

        workload_name = splitext(basename(reader.get_path()))[0]
        path = self._resultsDir + '/injection-' + workload_name + '-' + addr[0] + '_' + str(addr[1]) + '.csv'
        self._writer = ExecutionLogWriter(path)
        self._writer.write_entry(msg)

        endReached = False
        pendingTasks = set()
        pendingTasks.add(task.seqNum)

        while not endReached or len(pendingTasks) > 0:
            while self._client.peek_msg_queue() > 0:
                addr, msg = self._client.pop_msg_queue()
                self._writer.write_entry(msg)
                type = msg[MessageBuilder.FIELD_TYPE]
                if type == MessageBuilder.STATUS_START:
                    InjectorClient.logger.info("Task %s started on host %s" % (msg[MessageBuilder.FIELD_DATA], formatipport(addr)))
                elif type == MessageBuilder.STATUS_END:
                    InjectorClient.logger.info("Task %s terminated successfully on host %s" % (
                    msg[MessageBuilder.FIELD_DATA], formatipport(addr)))
                    pendingTasks.discard(msg[MessageBuilder.FIELD_SEQNUM])
                elif type == MessageBuilder.STATUS_ERR:
                    InjectorClient.logger.warning("Task %s terminated with error code %s on host %s" % (
                    msg[MessageBuilder.FIELD_DATA], str(msg[MessageBuilder.FIELD_ERR]), formatipport(addr)))
                    pendingTasks.discard(msg[MessageBuilder.FIELD_SEQNUM])

            now_timestamp = start_timestamp + (time() - start_timestamp_abs)

            while not endReached and task.timestamp < now_timestamp + self._preSendInterval:
                msg = MessageBuilder.command_start(task.args, task.duration, task.seqNum, task.timestamp, task.isFault)
                self._client.broadcast_msg(msg)
                pendingTasks.add(task.seqNum)
                task = reader.read_entry()
                if task is None:
                    endReached = True
                    reader.close()

            sleep(self._sleepPeriod)

        msg = MessageBuilder.command_session(0, end=True)
        self._client.broadcast_msg(msg)
        addr, msg = self._client.pop_msg_queue()
        if msg[MessageBuilder.FIELD_TYPE] == MessageBuilder.ACK_YES:
            InjectorClient.logger.info("Injection session closed with host %s" % formatipport(addr))
        else:
            InjectorClient.logger.error("Ack expected from host %s, got %s" % (formatipport(addr), msg[MessageBuilder.FIELD_TYPE]))

        self._writer.write_entry(msg)
        self._writer.close()

    def _signalhandler(self, sig, frame):
        """
        A signal handler to perform a graceful exit procedure on SIGINT 
        """
        if sig == signal.SIGINT:
            InjectorClient.logger.info('Exit requested by user. Cleaning up...')
            self._client.stop()
            InjectorClient.logger.info('Injection client stopped by user!')
            exit()

