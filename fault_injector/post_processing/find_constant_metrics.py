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

from csv import DictReader
import argparse


def findConstantMetrics(inpath):
    """
    Simple function that checks which metrics in a dictionary (read from a CSV) are constant and which change over time.
    As a reference, the first record read from the file is used

    :param inpath: The path to the CSV file that must be analyzed
    :return: The list of metrics (keys) that are constant in the file
    """
    infile = open(inpath, 'r')
    reader = DictReader(infile)
    try:
        metricSet = next(reader)
    except (StopIteration, IOError):
        infile.close()
        return []
    line = metricSet
    while line is not None:
        metricsToRemove = []
        for k in metricSet.keys():
            if line[k] != metricSet[k]:
                metricsToRemove.append(k)
        for m in metricsToRemove:
            metricSet.pop(m)
        try:
            line = next(reader)
        except (StopIteration, IOError):
            line = None
    infile.close()
    return list(metricSet.keys())


# This script analyzes CSV files containing performance metrics, and returns the list of metrics that are constant
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Fin-J Constant Metrics Search Tool")
    parser.add_argument("-f", action="store", dest="source", type=str, default=None, help="Path to the metric CSV file to be analyzed.")
    args = parser.parse_args()
    if args.source is None:
        print("You must supply the path to the metrics file that must be analyzed!")
        exit(-1)
    in_path = args.source
    constantMetrics = findConstantMetrics(in_path)
    print("Constant metrics found:")
    print(constantMetrics)
    exit(0)
