from fault_injector.workload_generator.element_generator import ElementGenerator
from fault_injector.io.writer import CSVWriter
from fault_injector.io.task import Task
from scipy.stats import norm
from numpy.random import choice
from os.path import split


class WorkloadGenerator:
    """
    Class that allows to generate full workloads for fault injection, starting from a specification of fault programs
    and benchmarks to be used.
    """

    PROBE_PREFIX = '/probe-'

    def __init__(self, path, fault_overlap=False, bench_overlap=False, write_probe=True):
        """
        Constructor for the class

        :param path: Path of the output file for the workload
        :param fault_overlap: Boolean flag. If False, the workload will have at most one fault running at all times.
        :param bench_overlap: Boolean flag. If False, the workload will have at most one benchmark running at all times.
        :param write_probe: Boolean flag. If True, a "probe" workload file is written alongside the workload. This file
            contains one entry for each fault/benchmark type, with a very short duration. It can be used to test the
            correct functionality or path of the programs before running the entire workload.
        """
        self._fault_overlap = fault_overlap
        self._bench_overlap = bench_overlap
        self._probe = write_probe
        self._path = path
        path_split, fname = split(path)
        self._probe_path = path_split + WorkloadGenerator.PROBE_PREFIX + fname
        self._faultTimeGenerator = ElementGenerator()
        self._faultDurGenerator = ElementGenerator()
        self._benchDurGenerator = ElementGenerator()
        self._benchTimeGenerator = ElementGenerator()

        # By default, the fault and benchmarks durations and arrival times are generated according to Normal
        # distributions with reasonable values.
        self._faultDurGenerator.set_distribution(norm(300, 2))
        self._faultTimeGenerator.set_distribution(norm(600, 2))
        self._benchDurGenerator.set_distribution(norm(1800, 2))
        self._benchTimeGenerator.set_distribution(norm(2400, 2))

# Properties used to regulate access to the internal statistical generators

    @property
    def faultTimeGenerator(self):
        return self._faultTimeGenerator

    @faultTimeGenerator.setter
    def faultTimeGenerator(self, el):
        pass

    @property
    def faultDurGenerator(self):
        return self._faultDurGenerator

    @faultDurGenerator.setter
    def faultDurGenerator(self, el):
        pass

    @property
    def benchTimeGenerator(self):
        return self._benchTimeGenerator

    @benchTimeGenerator.setter
    def benchTimeGenerator(self, el):
        pass

    @property
    def benchDurGenerator(self):
        return self._benchDurGenerator

    @benchDurGenerator.setter
    def benchDurGenerator(self, el):
        pass

# -------------------------------------------------------------------------

    def autoset_bench_generators(self, busy_time=0.75, num_tasks=20, span_limit=36000):
        """
        Sets the internal duration and inter-arrival time generators for benchmark tasks automatically, using some
        simple constraints.

        Provides a specular approach to explicitly defining the distributions used for generation.

        :param busy_time: The proportion in [0,1] of the workload's time span for which the system must be in
            a busy state, i.e. running benchmarks.
        :param num_tasks: The desired number of total, distinguished benchmark tasks to be generated.
        :param span_limit: The predicted time span of the final workload.
        """
        if busy_time < 0 or busy_time > 1:
            raise ValueError("Busy_time must be between 0 and 1!")
        var_factor = 0.01
        # We compute the total benchmark time with respect to its total time span
        bench_time = span_limit * busy_time
        # We compute the average length of each benchmark task
        bench_len = bench_time / num_tasks
        # We then compute the inter-benchmark time, in which the system will be idling
        inter_bench_time = bench_len + ((span_limit - bench_time) / num_tasks)
        # From the parameters defined above we set two Normal distributions for the duration and inter-arrival times
        self._benchDurGenerator.set_distribution(norm(bench_len, bench_len * var_factor))
        self._benchTimeGenerator.set_distribution(norm(inter_bench_time, inter_bench_time * var_factor))

    def autoset_fault_generators(self, busy_time=0.6, num_tasks=2000, span_limit=36000):
        """
        Sets the internal duration and inter-arrival time generators for fault tasks automatically, using some
        simple constraints.

        Provides a specular approach to explicitly defining the distributions used for generation.

        :param busy_time: The proportion in [0,1] of the workload's time span for which the system must be in
            a faulty state, i.e. running fault programs.
        :param num_tasks: The desired number of total, distinguished fault program tasks to be generated.
        :param span_limit: The predicted time span of the final workload.
        """
        if busy_time < 0 or busy_time > 1:
            raise ValueError("Busy_time must be between 0 and 1!")
        var_factor = 0.01
        # The logic of the method is identical as in autoset_bench_generators
        fault_time = span_limit * busy_time
        fault_len = fault_time / num_tasks
        inter_fault_time = fault_len + ((span_limit - fault_time) / num_tasks)
        self._faultDurGenerator.set_distribution(norm(fault_len, fault_len * var_factor))
        self._faultTimeGenerator.set_distribution(norm(inter_fault_time, inter_fault_time * var_factor))

    def generate(self, faults, benchmarks, fault_p=None, bench_p=None, span_limit=36000, size_limit=None):
        """
        Generates a full workload consisting of benchmark and fault program tasks, in CSV format.

        :param faults: The list of fault program paths to be used. It is HIGHLY suggested that each entry contain a
            Python formatting field ({}) in order to allow embedding the duration of the task in the command. This
            implies that all fault programs should accept duration specifications (in seconds) in their arguments. This
            is a VERY important fail-safe, and prevents orphan process situations in unexpected scenarios.
        :param benchmarks: The list of benchmark program commands/paths to be used.
        :param fault_p: Optional. It is a list containing a probability for each fault entry, and must thus be of the
            same length as faults.
        :param bench_p: Optional. It is a list containing a probability for each benchmark entry, and must thus be of
            the same length as benchmarks.
        :param span_limit: The time limit for the workload's duration, expressed in seconds
        :param size_limit: Optional. The size limit of the workload, in terms of tasks. When both span_limit and
            size_limit are active, the generation stops as soon as whichever limit is reached first.
        """
        if span_limit is None:
            # Argument correctness checks
            raise AttributeError('Span limit cannot be None!')
        if fault_p is None or len(fault_p) != len(faults):
            fault_p = [1 / len(faults)] * len(faults)
        if bench_p is None or len(bench_p) != len(benchmarks):
            bench_p = [1 / len(benchmarks)] * len(benchmarks)

        # The list of benchmark tasks is generated and stored beforehand
        bench_list = self._pregen_benchmarks(benchmarks, bench_p, span_limit, size_limit)

        writer = CSVWriter(self._path)
        cur_size = 0
        cur_span = 0
        cur_dur = 0

        while (size_limit is None or cur_size < size_limit) and cur_span < span_limit:
            # We draw a new inter-arrival time for the next fault
            next_ttf = self.faultTimeGenerator.pick()
            # If faults cannot overlap, the inter-arrival time is forced to be beyond the duration of the previous fault
            # This could slightly alter the final distribution
            while not self._fault_overlap and cur_dur >= next_ttf:
                next_ttf += self.faultTimeGenerator.pick()
            cur_span += next_ttf
            # We draw a new duration value for the fault
            cur_dur = self.faultDurGenerator.pick()

            # We build the corresponding Task object, and draw a random fault entry from the faults list
            t = Task(duration=int(cur_dur), timestamp=int(cur_span), isFault=True)
            t.args = choice(faults, p=fault_p).format(t.duration)

            # At each generated faults, we first pop and write all benchmarks that come earlier. This ensures that
            # the final workload is timestamp-ordered
            while(len(bench_list) > 0) and bench_list[0].timestamp < t.timestamp:
                b = bench_list.pop(0)
                b.seqNum = cur_size
                writer.write_entry(b)
                cur_size += 1

            # We write the fault's task and bind a sequence number to it
            t.seqNum = cur_size
            writer.write_entry(t)
            cur_size += 1

        writer.close()

        if self._probe:
            self._write_probe(self._probe_path, faults, benchmarks)

    def _pregen_benchmarks(self, benchmarks, bench_p=None, span_limit=36000, size_limit=None):
        """
        Generates and returns a list of benchmark tasks

        :param benchmarks: The list of benchmark commands/paths to be used
        :param bench_p: A list of probabilities for each benchmark command
        :param span_limit: The time limit of the workload
        :param size_limit: The size limit of the workload
        :return: A list of benchmark-related Task objects
        """
        cur_size = 0
        cur_span = 0
        cur_dur = 0
        bench_list = []

        # The internal logic of the algorithm is identical as in generate()
        while (size_limit is None or cur_size < size_limit) and cur_span < span_limit:
            next_ttf = self.benchTimeGenerator.pick()
            while not self._bench_overlap and cur_dur >= next_ttf:
                next_ttf += self.benchTimeGenerator.pick()
            cur_span += next_ttf
            cur_dur = self.benchDurGenerator.pick()

            t = Task(duration=int(cur_dur), timestamp=int(cur_span), isFault=False)
            t.args = choice(benchmarks, p=bench_p).format(t.duration)

            t.seqNum = cur_size
            bench_list.append(t)
            cur_size += 1

        return bench_list

    def _write_probe(self, path, faults, benchmarks):
        """
        Writes the probe workload file, if the write_probe option is enabled.

        :param path: The path to the probe workload file
        :param faults: The list of fault program paths
        :param benchmarks: The list of benchmark commands/paths
        """
        writer = CSVWriter(path)

        cur_span = 0
        cur_size = 0
        fix_dur = 5

        # This method write one single entry for each command type, with a low fixed duration (by default, 5 secs)
        for f in faults:
            t = Task(args=f.format(fix_dur), duration=fix_dur, timestamp=cur_span, isFault=True, seqNum=cur_size)
            writer.write_entry(t)
            cur_span += fix_dur
            cur_size += 1

        for b in benchmarks:
            t = Task(args=b, duration=fix_dur, timestamp=cur_span, isFault=False, seqNum=cur_size)
            writer.write_entry(t)
            cur_span += fix_dur
            cur_size += 1

        writer.close()
