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
    STATUS_END = 'status_end'
    STATUS_ERR = 'status_err'

    COMMAND_START = 'command_start'
    COMMAND_START_SESSION = 'command_session_s'
    COMMAND_SET_TIME = 'command_set_time'
    COMMAND_END_SESSION = 'command_session_e'
    COMMAND_TERMINATE = 'command_term'

    # Identifiers for the fields of the message
    FIELD_TYPE = 'type'
    FIELD_DATA = 'args'
    FIELD_SEQNUM = 'seqNum'
    FIELD_TIME = 'timestamp'
    FIELD_DUR = 'duration'
    FIELD_ISF = 'isFault'
    FIELD_ERR = 'error'

    # List of all available fields
    FIELDS = [FIELD_TIME, FIELD_TYPE, FIELD_DATA, FIELD_SEQNUM, FIELD_DUR, FIELD_ISF, FIELD_ERR]

    @staticmethod
    def ack(timestamp, positive=True):
        msg = {}
        msg[MessageBuilder.FIELD_TYPE] = MessageBuilder.ACK_YES if positive else MessageBuilder.ACK_NO
        msg = MessageBuilder._build_fields(msg, None, None, None, timestamp)
        return msg

    @staticmethod
    def command_set_time(timestamp):
        msg = {}
        msg[MessageBuilder.FIELD_TYPE] = MessageBuilder.COMMAND_SET_TIME
        msg = MessageBuilder._build_fields(msg, None, None, None, timestamp)
        return msg

    @staticmethod
    def command_session(timestamp, end=False):
        msg = {}
        msg[MessageBuilder.FIELD_TYPE] = MessageBuilder.COMMAND_START_SESSION if not end else MessageBuilder.COMMAND_END_SESSION
        msg = MessageBuilder._build_fields(msg, None, None, None, timestamp)
        return msg

    @staticmethod
    def command_terminate():
        msg = {}
        msg[MessageBuilder.FIELD_TYPE] = MessageBuilder.COMMAND_TERMINATE
        msg = MessageBuilder._build_fields(msg, None, None, None, None)
        return msg

    @staticmethod
    def command_start(args, duration, seqNum, timestamp, isFault):
        msg = {MessageBuilder.FIELD_TYPE: MessageBuilder.COMMAND_START}
        msg = MessageBuilder._build_fields(msg, args, duration, seqNum, timestamp, isFault)
        return msg

    @staticmethod
    def status_start(args, duration, seqNum, timestamp, isFault):
        msg = {MessageBuilder.FIELD_TYPE: MessageBuilder.STATUS_START}
        msg = MessageBuilder._build_fields(msg, args, duration, seqNum, timestamp, isFault)
        return msg

    @staticmethod
    def status_end(args, duration, seqNum, timestamp, isFault):
        msg = {MessageBuilder.FIELD_TYPE: MessageBuilder.STATUS_END}
        msg = MessageBuilder._build_fields(msg, args, duration, seqNum, timestamp, isFault)
        return msg

    @staticmethod
    def status_error(args, duration, seqNum, timestamp, isFault, error):
        msg = {MessageBuilder.FIELD_TYPE: MessageBuilder.STATUS_ERR}
        msg = MessageBuilder._build_fields(msg, args, duration, seqNum, timestamp, isFault, error)
        return msg

    @staticmethod
    def _build_fields(msg, args=None, duration=None, seqNum=None, timestamp=None, isFault=None, error=None):
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
        if error is not None:
            msg[MessageBuilder.FIELD_ERR] = error
        return msg
