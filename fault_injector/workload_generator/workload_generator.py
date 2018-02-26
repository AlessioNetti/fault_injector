from fault_injector.workload_generator.element_generator import ElementPicker
from fault_injector.io.writer import CSVWriter
from fault_injector.io.task import Task
from scipy.stats import norm
from random import uniform


class WorkloadGenerator:

    def __init__(self, path, busy_time=0.75, rr_benches=False, rr_faults=False, fault_overlap=False):
        self._rr_fault = rr_faults
        self._rr_bench = rr_benches
        self._busy_time = busy_time
        self._fault_overlap = fault_overlap
        self._path = path
        self._timeGenerator = ElementPicker()
        self._durationGenerator = ElementPicker()
        self._durationGenerator.set_distribution(norm(300, 2))
        self._rr_indexes = {}

    @property
    def timeGenerator(self):
        return self._timeGenerator

    @timeGenerator.setter
    def timeGenerator(self, el):
        pass

    @property
    def durationGenerator(self):
        return self._durationGenerator

    @durationGenerator.setter
    def durationGenerator(self, el):
        pass

    def generate(self, faults, benchmarks, size_limit=1000, span_limit=None):
        if size_limit is None and span_limit is None:
            raise AttributeError('Size limit and Span limit cannot be both None!')

        writer = CSVWriter(self._path)
        cur_size = 0
        cur_span = 0
        cur_dur = 0

        while (size_limit is None or cur_size < size_limit) and (span_limit is None or cur_span < span_limit):
            next_ttf = self.timeGenerator.pick()
            while not self._fault_overlap and cur_dur >= next_ttf:
                next_ttf += self.timeGenerator.pick()
            cur_span += next_ttf

            cur_dur = self.durationGenerator.pick()
            while cur_dur <= 0:
                cur_dur = self.durationGenerator.pick()

            t = Task()
            t.duration = int(cur_dur)
            t.timestamp = int(cur_span)
            t.isFault = True
            t.seqNum = cur_size
            t.args = self._pick_entry(faults, self._rr_fault).format(t.duration)
            writer.write_entry(t)

            cur_size += 1

        writer.close()

    def _pick_entry(self, l, rr):
        if rr:
            el = l[self._rr_indexes[id(l)]]
            self._rr_indexes[id(l)] = (self._rr_indexes[id(l)] + 1) % len(l)
        else:
            idx = int(uniform(0, len(l)))
            if idx >= len(l):
                idx = len(l) - 1
            el = l[idx]
        return el
