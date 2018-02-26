from fault_injector.workload_generator.element_generator import ElementPicker
from fault_injector.io.writer import CSVWriter
from fault_injector.io.task import Task
from scipy.stats import norm
from random import uniform


class WorkloadGenerator:

    def __init__(self, path, limit_size=1000, limit_span=86400, rr_selection=False, fault_overlap=False):
        self._rr = rr_selection
        self._fault_overlap = fault_overlap
        self._size = limit_size
        self._span = limit_span
        self._path = path
        self._timeGenerator = ElementPicker()
        self._durationGenerator = ElementPicker()
        self._durationGenerator.set_distribution(norm, 300, 2)
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

    def generate(self, faults, benchmarks):
        writer = CSVWriter(self._path)

        cur_size = 0
        cur_span = 0
        cur_dur = 0

        while cur_size < self._size and cur_span < self._span:
            next_ttf = self.timeGenerator.pick()
            while not self._fault_overlap and cur_dur >= next_ttf:
                next_ttf += self.timeGenerator.pick()
            cur_span += next_ttf

            cur_dur = self.durationGenerator.pick()
            while cur_dur <= 0:
                cur_dur = self.durationGenerator.pick()

            t = Task()
            t.duration = cur_dur
            t.timestamp = cur_span
            t.isFault = True
            t.seqNum = cur_size
            t.args = self._pick_entry(faults).format(cur_dur)
            writer.write_entry(t)

            cur_size += 1

        writer.close()

    def _pick_entry(self, l):
        if self._rr:
            el = l[self._rr_indexes[l]]
            self._rr_indexes[l] = (self._rr_indexes[l] + 1) % len(l)
        else:
            idx = int(uniform(0, len(l)))
            if idx >= len(l):
                idx = len(l) - 1
            el = l[idx]
        return el
