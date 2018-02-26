from scipy.stats import rv_continuous
import matplotlib.pyplot as plt
import numpy as np


class ElementPicker:

    def __init__(self):
        self._dist = None
        self._dist_params = None
        self._data = None
        self._value_range = None
        self._max_tries = 10000

    @property
    def value_range(self):
        return self._value_range

    @value_range.setter
    def value_range(self, v):
        if isinstance(v, (tuple, list)) and len(v) > 1 and v[0] < v[1]:
            self._value_range = tuple(v)

    def set_distribution(self, dist, *params):
        if dist is not None and isinstance(dist, rv_continuous):
            self._dist = dist
            self._dist_params = params
            self._data = None

    def fit_data(self, dist, data):
        if dist is not None and isinstance(dist, rv_continuous) and isinstance(data, (list, tuple)):
            data_range = (min(data), max(data))
            if self._value_range is not None:
                scale = (self._value_range[1] - self._value_range[0]) / (max(data) - min(data))
                self._data = [self._value_range[0] + (d - data_range[0]) * scale for d in data]
            else:
                self._data = data
            self._dist_params = dist.fit(data)
            self._dist = dist

    def show_fit(self, range=None):
        if range is None or not isinstance(range, (tuple, list)) or len(range) < 2:
            range = (1, 10) if self.value_range is None else self.value_range
        num_points = 1000
        xpoints = np.linspace(range[0], range[1], num_points)

        fig, ax = plt.subplots(figsize=(7, 5))

        if self._data is not None:
            ax.hist(self._data, normed=True)
        if self._dist is not None:
            plt.plot(xpoints, self._dist.pdf(xpoints, *self._dist_params))
        ax.set_xlim(left=range[0], right=range[1], emit=True, auto=False)
        plt.title("Fit of the Distribution")
        plt.show()

    def pick(self):
        el = self._dist.rvs(*self._dist_params) if self._dist is not None else None
        if el is not None and self.value_range is not None:
            tries = 1
            while tries < self._max_tries and (el < self.value_range[0] or el > self.value_range[1]):
                el = self._dist.rvs(*self._dist_params)
                tries += 1
            if tries >= self._max_tries:
                raise ValueError('Maximum number of generation tries reached. Check parameters of the distribution.')
        return
