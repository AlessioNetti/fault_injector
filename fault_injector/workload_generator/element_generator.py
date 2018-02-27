from scipy.stats import rv_continuous
# Hackish import because of Scipy's crap interface
from scipy.stats._distn_infrastructure import rv_frozen
import matplotlib.pyplot as plt
import numpy as np


class ElementPicker:

    def __init__(self, trim_zeros=True):
        self._dist = None
        self._data = None
        self._trimZeros = trim_zeros
        self._maxTries = 10000

    def set_distribution(self, dist):
        if dist is not None and isinstance(dist, rv_frozen):
            self._dist = dist
            self._data = None
        else:
            print(dist)

    def fit_data(self, dist, data, loc=None, scale=1):
        if dist is not None and isinstance(dist, rv_continuous) and isinstance(data, (list, tuple)):
            if loc is not None:
                shift = np.mean(data) - loc
                data = [d - shift for d in data]
            if scale != 1 and scale > 0:
                data_m = np.mean(data)
                data = [data_m + (d - data_m) * scale for d in data]
            self._data = data
            dist_params = dist.fit(self._data)
            self._dist = dist(*dist_params)

    def show_fit(self, val_range=(1, 10)):
        num_points = 1000
        xpoints = np.linspace(val_range[0], val_range[1], num_points)

        fig, ax = plt.subplots(figsize=(7, 5))

        if self._data is not None:
            ax.hist(self._data, normed=True)
        if self._dist is not None:
            plt.plot(xpoints, self._dist.pdf(xpoints))
            plt.title("Fit of the distribution")
        else:
            plt.title("No distribution currently set")
        ax.set_xlim(left=val_range[0], right=val_range[1], emit=True, auto=False)
        plt.show()

    def pick(self):
        el = self._dist.rvs() if self._dist is not None else None
        if el is not None and self._trimZeros and el <= 0:
            tries = 1
            while el <= 0 and tries < self._maxTries:
                el = self._dist.rvs()
                tries += 1
            if tries >= self._maxTries:
                raise RuntimeError('Max number of tries reached while trimming negative numbers from the distribution!')
        return el
