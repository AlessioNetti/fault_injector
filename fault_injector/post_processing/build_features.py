from csv import DictWriter, DictReader
from scipy.stats import kurtosis, skew
from collections import deque
from copy import copy
import argparse
import numpy as np

fieldBlacklist = ['#Time', 'Time_usec', 'ProducerName', 'component_id', 'job_id']
timeLabel = '#Time'
outputTimeLabel = 'timestamp'
perCoreLabel = 'per_core_'


def computeDerivatives(oldEntry, newEntry):
    diff = {}
    for k, v in newEntry.items():
        diff[k] = v - oldEntry[k]
    return diff


def getStatistics(myData, metricName):
    percentiles = [5, 25, 50, 75, 95]
    percentileLabel = '_perc'
    stats = {}
    stats[metricName + '_avg'] = np.asscalar(np.average(myData))
    stats[metricName + '_min'] = np.asscalar(np.min(myData))
    stats[metricName + '_max'] = np.asscalar(np.max(myData))
    stats[metricName + '_std'] = np.asscalar(np.std(myData))
    stats[metricName + '_skew'] = np.asscalar(skew(myData))
    stats[metricName + '_kurt'] = np.asscalar(kurtosis(myData))
    percs = np.percentile(myData, percentiles)
    for ind, p in enumerate(percs):
        stats[metricName + percentileLabel + str(percentiles[ind])] = p
    return stats


def isGoodPerCoreMetric(k, core):
    return perCoreLabel not in k or str(core) in k if core is not None else True


def updateAndFilter(dest, src, core=None):
    goodVals = {k: float(v) for k, v in src.items() if k not in fieldBlacklist and isGoodPerCoreMetric(k, core)}
    dest.update(goodVals)
    return dest


def buildFeatures(inpaths, out, window=60, step=1, core=None):
    infiles = {}
    readers = {}
    pilotReader = None
    for ind, p in enumerate(inpaths):
        if ind == 0:
            infile = open(p, 'r')
            infiles[p] = infile
            pilotReader = DictReader(infile)
        else:
            infile = open(p, 'r')
            infiles[p] = infile
            readers[p] = DictReader(infile)

    entriesQueue = deque()
    currStep = 0
    lastEntry = {}
    outfile = None
    writer = None
    while True:
        # With this approach metrics coming from different files MAY slightly dis-align over time, even if they start
        # from the same timestamp and have the same step
        try:
            entry = next(pilotReader)
        except (StopIteration, IOError):
            break
        currTimestamp = int(entry[timeLabel].split('.')[0])
        lastEntry = updateAndFilter(lastEntry, entry, core)

        for reader in readers.values():
            try:
                entry = next(reader)
            except (StopIteration, IOError):
                continue
            lastEntry = updateAndFilter(lastEntry, entry, core)
        currDerivative = computeDerivatives(entriesQueue[0][1], lastEntry) if len(entriesQueue) > 0 else None
        entriesQueue.appendleft((currTimestamp, copy(lastEntry), currDerivative))
        if len(entriesQueue) > window:
            entriesQueue.pop()
        currStep += 1
        if currStep > step and len(entriesQueue) >= window:
            currStep = 0
            feature = {}
            for k in lastEntry.keys():
                # Processing statistical features for all entries in the queue
                feature.update(getStatistics([en[1][k] for en in entriesQueue], k))
                # Processing statistical features for first-order derivative entries in the queue
                feature.update(getStatistics([en[2][k] for en in entriesQueue if en[2] is not None], k + '_der'))
                feature[outputTimeLabel] = np.asscalar(np.average([en[0] for en in entriesQueue]))
                if writer is None:
                    outfile = open(out, 'w')
                    writer = DictWriter(outfile, fieldnames=list(feature.keys()))
                    fieldict = {k: k for k in writer.fieldnames}
                    writer.writerow(fieldict)
                writer.writerow(feature)

    for f in infiles.values():
        f.close()
    outfile.close()


# This script takes as input a list of CSV performance metric files, and builds features by considering all available
# metrics, and by computing statistical descriptors over a specified aggregation window
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Fin-J CSV Features Builder Tool")
    parser.add_argument("-f", action="store", dest="sources", type=str, default=None,
                        help="Path to the CSV files to be analyzed, separated by comma.")
    parser.add_argument("-w", action="store", dest="window", type=int, default=60,
                        help="Length of the aggregation window, in samples.")
    parser.add_argument("-s", action="store", dest="step", type=int, default=1,
                        help="Step between adjacent features, in samples.")
    parser.add_argument("-o", action="store", dest="out", type=str, default="out.csv",
                        help="Path to the output file.")
    parser.add_argument("-c", action="store", dest="core", type=int, default=None,
                        help="Selects a single core ID for which per-core metrics must be used.")
    args = parser.parse_args()
    sources = args.sources.split(',') if args.sources is not None else None
    if sources is None:
        print("You must supply at least one path to a CSV file that must be analyzed!")
        exit(-1)
    if args.window < 1:
        args.window = 1
    if args.step < 1:
        args. step = 1
    buildFeatures(sources, args.out, args.window, args.step, args.core)
    exit(0)
