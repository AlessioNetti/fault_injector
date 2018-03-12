from fault_injector.network.msg_builder import MessageBuilder
from fault_injector.util.misc import VALUE_NO_CORES


class Task:
    """
    Struct-like class for easy access to task-related parameters
    """

    # Hardcoded value to represent Tasks that have no bounded duration
    VALUE_DUR_NO_LIM = 0

    def __init__(self, args='', timestamp=0, duration=0, seqNum=0, isFault=False, cores=VALUE_NO_CORES):
        self.args = args
        self.timestamp = timestamp
        self.duration = duration
        self.seqNum = seqNum
        self.isFault = isFault
        self.cores = cores

    @staticmethod
    def dict_to_task(entry):
        """
        Converts a dictionary to a Task object. Mind that the dictionary MUST contain all of the attributes in the Task
        class, with the same naming
        
        :param entry: a dictionary
        :return: a Task object
        """
        if not isinstance(entry, dict):
            return None
        t = Task()
        try:
            for a in vars(t):
                v_type = type(getattr(t, a))
                v = v_type(entry[a]) if v_type != bool else entry[a] == 'True'
                setattr(t, a, v)
            return t
        except KeyError:
            return None

    @staticmethod
    def task_to_dict(task):
        """
        Performs reverse conversion, from Task to dictionary
        
        :param task: the task object
        :return: the output dictionary
        """
        if not isinstance(task, Task):
            return None
        d = {}
        for a in vars(task):
            d[a] = getattr(task, a)
        return d

    @staticmethod
    def msg_to_task(msg):
        """
        Converts a dictionary created by MessageBuilder to a Task object
        
        :param msg: the input dictionary
        :return: the Task object
        """
        if not isinstance(msg, dict):
            return None
        t = Task()
        t.args = msg[MessageBuilder.FIELD_DATA]
        t.isFault = msg[MessageBuilder.FIELD_ISF]
        t.seqNum = msg[MessageBuilder.FIELD_SEQNUM]
        t.timestamp = msg[MessageBuilder.FIELD_TIME]
        t.duration = msg[MessageBuilder.FIELD_DUR]
        t.cores = msg[MessageBuilder.FIELD_CORES]
        return t
