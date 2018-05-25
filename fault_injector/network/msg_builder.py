class MessageBuilder:
    """
    This class allows to build messages starting from pre-defined templates.
    
    The provided static methods allow to build dictionaries that can be sent in json format as messages through the 
    Client and Server entities. There is a method for each type of message expected in the communication protocol.
    """

    # Identifiers for each type of message
    ACK_YES = 'ack_yes'
    ACK_NO = 'ack_no'

    STATUS_START = 'status_start'
    STATUS_RESTART = 'status_restart'
    STATUS_END = 'status_end'
    STATUS_ERR = 'status_err'
    STATUS_GREET = 'status_greet'
    STATUS_RESET = 'status_reset'
    STATUS_LOST = 'detected_lost'
    STATUS_RESTORED = 'detected_restored'

    COMMAND_START = 'command_start'
    COMMAND_START_SESSION = 'command_session_s'
    COMMAND_SET_TIME = 'command_set_time'
    COMMAND_CORRECT_TIME = 'command_correct_time'
    COMMAND_END_SESSION = 'command_session_e'
    COMMAND_TERMINATE = 'command_term'
    COMMAND_GREET = 'command_greet'

    # Identifiers for the fields of the message
    FIELD_TYPE = 'type'
    FIELD_DATA = 'args'
    FIELD_SEQNUM = 'seqNum'
    FIELD_TIME = 'timestamp'
    FIELD_DUR = 'duration'
    FIELD_ISF = 'isFault'
    FIELD_OUTPUT = 'output'
    FIELD_ERR = 'error'
    FIELD_CORES = 'cores'

    # List of all available fields (except output, which is treated separately)
    FIELDS = [FIELD_TIME, FIELD_TYPE, FIELD_DATA, FIELD_SEQNUM, FIELD_DUR, FIELD_ISF, FIELD_CORES, FIELD_ERR]

    @staticmethod
    def ack(timestamp, positive=True, error=None):
        msg = {MessageBuilder.FIELD_TYPE: MessageBuilder.ACK_YES if positive else MessageBuilder.ACK_NO}
        if error is not None:
            msg[MessageBuilder.FIELD_ERR] = error
        msg = MessageBuilder._build_fields(msg, None, None, None, timestamp, None, None)
        return msg

    @staticmethod
    def command_greet(timestamp):
        msg = {MessageBuilder.FIELD_TYPE: MessageBuilder.COMMAND_GREET}
        msg = MessageBuilder._build_fields(msg, None, None, None, timestamp, None, None)
        return msg

    @staticmethod
    def command_set_time(timestamp):
        msg = {MessageBuilder.FIELD_TYPE: MessageBuilder.COMMAND_SET_TIME}
        msg = MessageBuilder._build_fields(msg, None, None, None, timestamp, None, None)
        return msg

    @staticmethod
    def command_correct_time(timestamp):
        msg = {MessageBuilder.FIELD_TYPE: MessageBuilder.COMMAND_CORRECT_TIME}
        msg = MessageBuilder._build_fields(msg, None, None, None, timestamp, None, None)
        return msg

    @staticmethod
    def command_session(timestamp, end=False):
        msg = {MessageBuilder.FIELD_TYPE: MessageBuilder.COMMAND_START_SESSION if not end else MessageBuilder.COMMAND_END_SESSION}
        msg = MessageBuilder._build_fields(msg, None, None, None, timestamp, None, None)
        return msg

    @staticmethod
    def command_terminate():
        msg = {MessageBuilder.FIELD_TYPE: MessageBuilder.COMMAND_TERMINATE}
        return msg

    @staticmethod
    def status_connection(timestamp, restored=False):
        msg = {MessageBuilder.FIELD_TYPE: MessageBuilder.STATUS_RESTORED if restored else MessageBuilder.STATUS_LOST}
        msg = MessageBuilder._build_fields(msg, None, None, None, timestamp, None, None)
        return msg

    @staticmethod
    def status_reset(timestamp):
        msg = {MessageBuilder.FIELD_TYPE: MessageBuilder.STATUS_RESET}
        msg = MessageBuilder._build_fields(msg, None, None, None, timestamp, None, None)
        return msg

    @staticmethod
    def status_greet(timestamp, num, active):
        msg = {MessageBuilder.FIELD_TYPE: MessageBuilder.STATUS_GREET}
        msg = MessageBuilder._build_fields(msg, num, None, None, timestamp, active, None)
        return msg

    @staticmethod
    def command_start(t):
        msg = {MessageBuilder.FIELD_TYPE: MessageBuilder.COMMAND_START}
        msg = MessageBuilder._build_fields(msg, t.args, t.duration, t.seqNum, t.timestamp, t.isFault, t.cores)
        return msg

    @staticmethod
    def status_start(t):
        msg = {MessageBuilder.FIELD_TYPE: MessageBuilder.STATUS_START}
        msg = MessageBuilder._build_fields(msg, t.args, t.duration, t.seqNum, t.timestamp, t.isFault, t.cores)
        return msg

    @staticmethod
    def status_restart(t, error=None):
        msg = {MessageBuilder.FIELD_TYPE: MessageBuilder.STATUS_RESTART}
        if error is not None:
            msg[MessageBuilder.FIELD_ERR] = error
        msg = MessageBuilder._build_fields(msg, t.args, t.duration, t.seqNum, t.timestamp, t.isFault, t.cores)
        return msg

    @staticmethod
    def status_end(t, output=None):
        msg = {MessageBuilder.FIELD_TYPE: MessageBuilder.STATUS_END}
        if output is not None:
            msg[MessageBuilder.FIELD_OUTPUT] = output
        msg = MessageBuilder._build_fields(msg, t.args, t.duration, t.seqNum, t.timestamp, t.isFault, t.cores)
        return msg

    @staticmethod
    def status_error(t, error, output=None):
        msg = {MessageBuilder.FIELD_TYPE: MessageBuilder.STATUS_ERR}
        if error is not None:
            msg[MessageBuilder.FIELD_ERR] = error
        if output is not None:
            msg[MessageBuilder.FIELD_OUTPUT] = output
        msg = MessageBuilder._build_fields(msg, t.args, t.duration, t.seqNum, t.timestamp, t.isFault, t.cores)
        return msg

    @staticmethod
    def _build_fields(msg, args=None, duration=None, seqNum=None, timestamp=None, isFault=None, cores=None):
        if args is not None:
            msg[MessageBuilder.FIELD_DATA] = args
        if duration is not None:
            msg[MessageBuilder.FIELD_DUR] = duration
        if seqNum is not None:
            msg[MessageBuilder.FIELD_SEQNUM] = seqNum
        if timestamp is not None:
            msg[MessageBuilder.FIELD_TIME] = int(timestamp)
        if isFault is not None:
            msg[MessageBuilder.FIELD_ISF] = isFault
        if cores is not None:
            msg[MessageBuilder.FIELD_CORES] = cores
        return msg
