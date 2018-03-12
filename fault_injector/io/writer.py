import csv, logging
from abc import ABC, abstractmethod
from fault_injector.io.task import Task
from fault_injector.network.msg_builder import MessageBuilder


class Writer(ABC):
    """
    Writer abstract class, for both workload and execution record writing
    """

    def __init__(self, path):
        """
        Constructor for the class
        
        :param path: Path of the output file
        """
        self._path = path

    def get_path(self):
        """
        Returns the path of the underlying file
        
        :return: A file path 
        """
        return self._path

    @abstractmethod
    def write_entry(self, entry):
        """
        Writes an entry to the output file, implementation-dependent
        
        :param entry: The entry object to be written
        """
        raise(NotImplementedError, 'This method must be implemented!')

    @abstractmethod
    def close(self):
        """
        Closes the writer file stream
        """
        raise (NotImplementedError, 'This method must be implemented!')


class CSVWriter(Writer):
    """
    Writer class for workloads in CSV format. To be used in tandem with the CSVReader class
    """

    # Logger for the class
    logger = logging.getLogger(__name__)

    DELIMITER_CHAR = ';'
    QUOTE_CHAR = '|'

    def __init__(self, path):
        """
        Constructor for the class
        
        :param path: Path of the output file
        """
        super().__init__(path)
        # The fields of the output file always correspond to those of the Task class
        self._fieldnames = sorted(list(vars(Task())))
        fieldict = {k: k for k in self._fieldnames}
        self._wfile = None
        try:
            self._wfile = open(self._path, 'w')
            self._writer = csv.DictWriter(self._wfile, fieldnames=self._fieldnames, delimiter=CSVWriter.DELIMITER_CHAR,
                                          quotechar=CSVWriter.QUOTE_CHAR)
            self._writer.writerow(fieldict)
        except (FileNotFoundError, IOError):
            CSVWriter.logger.error('Cannot write workload to path %s' % self._path)
            self._writer = None

    def write_entry(self, entry):
        """
        Writes a Task to the output file
        
        :param entry: the Task object that is to be converted and written to CSV
        :return: True if successful, False otherwise
        """
        if self._writer is None:
            CSVWriter.logger.error('No open file stream to write to')
            return False
        if not isinstance(entry, Task):
            CSVWriter.logger.error('Input Task to write_entry is malformed')
            return False
        try:
            d = Task.task_to_dict(entry)
            self._writer.writerow(d)
            self._wfile.flush()
            return True
        except (StopIteration, IOError):
            self._wfile.close()
            return False

    def close(self):
        """
        Closes the output file stream
        """
        if self._wfile is not None:
            self._wfile.close()
            self._writer = None


class ExecutionLogWriter(Writer):
    """
    Writer class for execution log records corresponding to injection or listening sessions
    """

    # Logger for the class
    logger = logging.getLogger(__name__)

    DELIMITER_CHAR = ';'
    QUOTE_CHAR = '|'
    NONE_VALUE = 'None'

    def __init__(self, path):
        """
        Constructor for the class
        
        :param path: path of the output file 
        """
        super().__init__(path)
        self._wfile = None
        # The fields written in the CSV file correspond to those of a MessageBuilder dictionary
        self._fieldnames = MessageBuilder.FIELDS
        fieldict = {k: k for k in self._fieldnames}
        try:
            self._wfile = open(self._path, 'w')
            self._writer = csv.DictWriter(self._wfile, fieldnames=self._fieldnames, delimiter=CSVWriter.DELIMITER_CHAR,
                                          quotechar=CSVWriter.QUOTE_CHAR, restval=ExecutionLogWriter.NONE_VALUE,
                                          extrasaction='ignore')
            self._writer.writerow(fieldict)
        except (FileNotFoundError, IOError):
            ExecutionLogWriter.logger.error('Cannot write execution log record to path %s' % self._path)
            self._writer = None

    def write_entry(self, entry):
        """
        Writes an entry to the execution log
        
        :param entry: a MessageBuilder dictionary
        :return: True if successful, False otherwise 
        """
        if self._writer is None:
            ExecutionLogWriter.logger.error('No open file stream to write to')
            return False
        if not isinstance(entry, dict):
            ExecutionLogWriter.logger.error('Input Dict to write_entry is malformed')
            return False
        try:
            self._writer.writerow(entry)
            self._wfile.flush()
            return True
        except (StopIteration, IOError):
            self._wfile.close()
            return False

    def close(self):
        """
        Closes the output file stream
        """
        if self._wfile is not None:
            self._wfile.close()
            self._writer = None
