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

from scipy.stats import rv_continuous
from scipy.stats.distributions import rv_frozen
from math import sqrt
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as plt
import numpy as np


class ElementGenerator:
    """
    This class encapsulates SciPy distribution objects, and provides easy to use tools to perform fitting and extract
    values from a statistical distribution.
    """

    def __init__(self, trim_zeros=True):
        """
        Constructor for the class

        :param trim_zeros: Boolean flag. If True, values less or equal than zero are never returned with pick()
        """
        self._dist = None
        self._data = None
        self._trimZeros = trim_zeros
        self._maxTries = 10000

    def set_distribution(self, dist):
        """
        Sets a statistical distribution to be used.

        :param dist: The distribution object. MUST be an rv_frozen SciPy object, which is a distribution with its
            parameters fixed.
        """
        if dist is not None and isinstance(dist, rv_frozen):
            self._dist = dist
            self._data = None
        else:
            raise ValueError('Invalid input types detected')

    def fit_data(self, dist, data, loc=None, scale=None):
        """
        Performs fitting over a given dataset by using the indicated distribution type.

        The resulting distribution is stored within the object for future use.

        :param dist: The distribution to be used for fitting. It MUST be an rv_continuous SciPy object
            (i.e. norm, exponweib)
        :param data: The data on which fitting must be performed. Must be a 1-dimensional Python list
        :param loc: Optional "location" parameter. If supplied, the data's mean is shifted to loc
        :param scale: Optional "scale" parameter. If supplied, the data's standard deviation is shifted to scale.
        """
        if dist is not None and isinstance(dist, rv_continuous) and isinstance(data, (list, tuple)):
            if loc is not None:
                shift = np.mean(data) - loc
                data = [d - shift for d in data]
            if scale is not None and scale >= 0:
                data_m = np.mean(data)
                data_std = np.std(data)
                data = [data_m + (d - data_m) * scale / data_std for d in data]
            self._data = data
            dist_params = dist.fit(self._data)
            self._dist = dist(*dist_params)
        else:
            raise ValueError('Invalid input types detected')

    def show_fit(self, val_range=(1, 10), n_bins=None, title='', xlabel='', ylabel='', out=None):
        """
        Displays a plot of the distribution's PDF, and an histogram of the data used for fitting (if any).

        :param val_range: Range of the plot on the X axis
        :param n_bins: The number of bins for the histogram, optional
        :param title: Title of the plot, optional
        :param xlabel: Label for the X axis, optional
        :param ylabel: Label for the Y axis, optional
        :param out: Path for the output plot file, optional
        """
        num_points = 1000
        fontsize = 12
        xpoints = np.linspace(val_range[0], val_range[1], num_points)

        fig, ax = plt.subplots(figsize=(7, 5))

        if self._data is not None:
            data_to_show = [d for d  in self._data if val_range[0] <= d <= val_range[1]]
            if n_bins is None or n_bins < 0:
                n_bins = int(sqrt(abs(val_range[1] - val_range[0])))
            ax.hist(data_to_show, normed=True, bins=n_bins)
        if self._dist is not None:
            plt.plot(xpoints, self._dist.pdf(xpoints))
            plt.title(title, fontsize=fontsize)
        else:
            plt.title("No distribution currently set", fontsize=fontsize)
        ax.set_xlim(left=val_range[0], right=val_range[1], emit=True, auto=False)
        ax.set_xlabel(xlabel, fontsize=fontsize)
        ax.set_ylabel(ylabel, fontsize=fontsize)
        plt.show()

        if out is not None:
            ff = PdfPages(out)
            ff.savefig(fig)
            ff.close()

    def pick(self):
        """
        Draws one value according to the underlying distribution.

        :return: One floating-point value drawn from a statistical distribution
        """
        el = self._dist.rvs() if self._dist is not None else None
        if el is not None and self._trimZeros and el <= 0:
            tries = 1
            while el <= 0 and tries < self._maxTries:
                el = self._dist.rvs()
                tries += 1
            if tries >= self._maxTries:
                raise RuntimeError('Max number of tries reached while trimming negative numbers from the distribution!')
        return el
