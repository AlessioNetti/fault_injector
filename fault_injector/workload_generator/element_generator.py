from scipy.stats import rv_continuous
# Hackish import because of Scipy's crap interface
from scipy.stats._distn_infrastructure import rv_frozen
import matplotlib.pyplot as plt
import numpy as np


class ElementPicker:

    def __init__(self):
        self._dist = None
        self._data = None
        self._max_tries = 10000

    def set_distribution(self, dist):
        if dist is not None and isinstance(dist, rv_frozen):
            self._dist = dist
            self._data = None
        else:
            print(dist)

    def fit_data(self, dist, data, loc=None):
        if dist is not None and isinstance(dist, rv_continuous) and isinstance(data, (list, tuple)):
            if loc is not None:
                shift = np.mean(data) - loc
                self._data = [d - shift for d in data]
            else:
                self._data = data
            dist_params = dist.fit(data)
            self._dist = dist(*dist_params)

    def show_fit(self, range=None):
        if range is None or not isinstance(range, (tuple, list)) or len(range) < 2:
            range = (1, 10)
        num_points = 1000
        xpoints = np.linspace(range[0], range[1], num_points)

        fig, ax = plt.subplots(figsize=(7, 5))

        if self._data is not None:
            ax.hist(self._data, normed=True)
        if self._dist is not None:
            plt.plot(xpoints, self._dist.pdf(xpoints))
        ax.set_xlim(left=range[0], right=range[1], emit=True, auto=False)
        plt.title("Fit of the Distribution")
        plt.show()

    def pick(self):
        return self._dist.rvs() if self._dist is not None else None
