from fault_injector.workload_generator.element_generator import ElementPicker
from fault_injector.io.writer import CSVWriter
from fault_injector.io.task import Task
from scipy.stats import norm
from numpy.random import choice
from os.path import split


class WorkloadGenerator:

    def __init__(self, path, fault_overlap=False, bench_overlap=False, write_probe=True):
        self._fault_overlap = fault_overlap
        self._bench_overlap = bench_overlap
        self._probe = write_probe
        self._path = path
        path_split, fname = split(path)
        self._probe_path = path_split + '/probe-' + fname
        self._rr_indexes = {}
        self._faultTimeGenerator = ElementPicker()
        self._faultDurGenerator = ElementPicker()
        self._benchDurGenerator = ElementPicker()
        self._benchTimeGenerator = ElementPicker()

        self._faultDurGenerator.set_distribution(norm(300, 2))
        self._faultTimeGenerator.set_distribution(norm(600, 2))
        self._benchDurGenerator.set_distribution(norm(1800, 2))
        self._benchTimeGenerator.set_distribution(norm(2400, 2))

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

    def autoset_bench_generators(self, busy_time=0.75, num_tasks=20, span_limit=36000):
        if busy_time < 0 or busy_time > 1:
            raise ValueError("Busy_time must be between 0 and 1!")
        var_factor = 0.01
        bench_time = span_limit * busy_time
        bench_len = bench_time / num_tasks
        inter_bench_time = bench_len + ((span_limit - bench_time) / num_tasks)
        self._benchDurGenerator.set_distribution(norm(bench_len, bench_len * var_factor))
        self._benchTimeGenerator.set_distribution(norm(inter_bench_time, inter_bench_time * var_factor))

    def autoset_fault_generators(self, busy_time=0.6, num_tasks=2000, span_limit=36000):
        if busy_time < 0 or busy_time > 1:
            raise ValueError("Busy_time must be between 0 and 1!")
        var_factor = 0.01
        fault_time = span_limit * busy_time
        fault_len = fault_time / num_tasks
        inter_fault_time = fault_len + ((span_limit - fault_time) / num_tasks)
        self._faultDurGenerator.set_distribution(norm(fault_len, fault_len * var_factor))
        self._faultTimeGenerator.set_distribution(norm(inter_fault_time, inter_fault_time * var_factor))

    def generate(self, faults, benchmarks, fault_p=None, bench_p=None, span_limit=36000, size_limit=None):
        if span_limit is None:
            raise AttributeError('Span limit cannot be None!')
        if fault_p is None or len(fault_p) != len(faults):
            fault_p = [1 / len(faults)] * len(faults)
        if bench_p is None or len(bench_p) != len(benchmarks):
            bench_p = [1 / len(benchmarks)] * len(benchmarks)

        bench_list = self._pregen_benchmarks(benchmarks, bench_p, span_limit, size_limit)

        writer = CSVWriter(self._path)
        cur_size = 0
        cur_span = 0
        cur_dur = 0

        while (size_limit is None or cur_size < size_limit) and cur_span < span_limit:
            next_ttf = self.faultTimeGenerator.pick()
            while not self._fault_overlap and cur_dur >= next_ttf:
                next_ttf += self.faultTimeGenerator.pick()
            cur_span += next_ttf

            cur_dur = self.faultDurGenerator.pick()

            t = Task()
            t.duration = int(cur_dur)
            t.timestamp = int(cur_span)
            t.isFault = True
            t.seqNum = cur_size
            t.args = choice(faults, p=fault_p).format(t.duration)
            cur_size += 1

            while(len(bench_list) > 0) and bench_list[0].timestamp < t.timestamp:
                b = bench_list.pop(0)
                writer.write_entry(b)

            writer.write_entry(t)

        writer.close()

        if self._probe:
            self._write_probe(self._probe_path, faults, benchmarks)

    def _pregen_benchmarks(self, benchmarks, bench_p, span_limit, size_limit):
        cur_size = 0
        cur_span = 0
        cur_dur = 0
        bench_list = []

        while (size_limit is None or cur_size < size_limit) and cur_span < span_limit:
            next_ttf = self.benchTimeGenerator.pick()
            while not self._bench_overlap and cur_dur >= next_ttf:
                next_ttf += self.benchTimeGenerator.pick()
            cur_span += next_ttf

            cur_dur = self.benchDurGenerator.pick()

            t = Task()
            t.duration = int(cur_dur)
            t.timestamp = int(cur_span)
            t.isFault = False
            t.seqNum = cur_size
            t.args = choice(benchmarks, p=bench_p).format(t.duration)

            cur_size += 1
            bench_list.append(t)

        return bench_list

    def _write_probe(self, path, faults, benchmarks):
        writer = CSVWriter(path)

        cur_span = 0
        fix_dur = 5

        for f in faults:
            t = Task()
            t.duration = fix_dur
            t.timestamp = cur_span
            t.args = f
            t.isFault = True
            writer.write_entry(t)
            cur_span += fix_dur

        for b in benchmarks:
            t = Task()
            t.duration = fix_dur
            t.timestamp = cur_span
            t.args = b
            t.isFault = False
            writer.write_entry(t)
            cur_span += fix_dur

        writer.close()
