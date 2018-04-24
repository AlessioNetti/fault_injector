from csv import DictReader
import argparse


# Simple function that checks which metrics in a dictionary (read from a CSV) are constant and which change over time.
# As a reference, the first record read from the file is used
def findConstantMetrics(inpath):
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
