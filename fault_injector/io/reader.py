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

import csv, logging
from abc import ABC, abstractmethod
from fault_injector.io.writer import CSVWriter
from fault_injector.io.task import Task


class Reader(ABC):
    """
    Abstract class for readers of workload and execution-related logs
    """

    def __init__(self, path):
        """
        Constructor for the class
        
        :param path: Path of the file to be read 
        """
        self._path = path

    def get_path(self):
        """
        Returns the path of the file that is being read
        
        :return: A file path 
        """
        return self._path

    @abstractmethod
    def read_entry(self):
        """
        Reads one entry from the specified input file
        
        :return: One entry, implementation-dependent 
        """
        raise(NotImplementedError, 'This method must be implemented!')

    @abstractmethod
    def close(self):
        """
        Closes the file stream
        """
        raise (NotImplementedError, 'This method must be implemented!')

    def _resolve_none_entries(self, entry):
        """
        Returns a dictionary starting from the input in which all entries matching the None keyword are converted to
        the None Python primitive

        :param entry: A dictionary to be filtered
        :return: The input dictionary, with all None values correctly assigned
        """
        newEntry = {}
        for k in entry.keys():
            newEntry[k] = entry[k] if entry[k] is not None and entry[k] != CSVWriter.NONE_VALUE else None
        return newEntry


class CSVReader(Reader):
    """
    This class reads CSV workload files. These files MUST contain all of the fields of the Task class, with their order
    and name specified in the first row of the file. 
    """

    # Logger for the class
    logger = logging.getLogger('CSVReader')

    def __init__(self, path):
        """
        Constructor for the class
        
        :param path: Path of the workload file
        """
        super().__init__(path)
        try:
            self._rfile = open(self._path, 'r')
            self._reader = csv.DictReader(self._rfile, delimiter=CSVWriter.DELIMITER_CHAR, quotechar=CSVWriter.QUOTE_CHAR,
                                          restval=CSVWriter.NONE_VALUE)
        except (FileNotFoundError, IOError):
            CSVReader.logger.error("Cannot read workload from path %s" % self._path)
            self._reader = None

    def read_entry(self):
        """
        Reads one Task entry from the CSV file
        
        :return: a Task object
        """
        if self._reader is None:
            return None
        try:
            line = next(self._reader)
        # These exceptions correspond to the stream reaching the end of the file
        except (StopIteration, IOError):
            self._rfile.close()
            return None
        # After reading the line, we strip all eventually present spaces and tabs
        filtered_line = {}
        for key, value in line.items():
            filtered_line[key.strip()] = value.strip()
        filtered_line = self._resolve_none_entries(filtered_line)
        # We convert the dict read from the line to a Task object
        task = Task.dict_to_task(filtered_line)
        if task is None:
            CSVReader.logger.error("Input workload entry is malformed: please check that the fields are named "
                                   "like the attributes of the Task class.")
        return task

    def close(self):
        """
        Closes the reader file stream
        """
        if self._rfile is not None:
            self._rfile.close()
            self._reader = None


class ExecutionLogReader(Reader):
    """
    Reader class for the execution logs produced by injection sessions of this tool
    """

    # Logger for the class
    logger = logging.getLogger('ExecutionLogReader')

    def __init__(self, path):
        """
        Constructor for the class
        
        :param path: Path of the execution log file
        """
        super().__init__(path)
        self._rfile = None
        try:
            self._rfile = open(self._path, 'r')
            self._reader = csv.DictReader(self._rfile, delimiter=CSVWriter.DELIMITER_CHAR,
                                          quotechar=CSVWriter.QUOTE_CHAR, restval=CSVWriter.NONE_VALUE)
        except (FileNotFoundError, IOError):
            ExecutionLogReader.logger.error('Cannot read execution log from path %s' % self._path)
            self._reader = None

    def read_entry(self):
        """
        Reads one entry from the execution log file
        
        :return: A dictionary corresponding to one built by MessageBuilder
        """
        if self._reader is None:
            return None
        try:
            line = next(self._reader)
        except (StopIteration, IOError):
            self._rfile.close()
            return None
        # After reading the line, we strip all eventually present spaces and tabs
        filtered_line = {}
        for key, value in line.items():
            filtered_line[key.strip()] = value.strip()
        filtered_line = self._resolve_none_entries(filtered_line)
        return filtered_line

    def close(self):
        """
        Closes the reader file stream
        """
        if self._rfile is not None:
            self._rfile.close()
            self._reader = None
