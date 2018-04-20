from fault_injector.io.writer import CSVWriter
from csv import DictWriter, DictReader
from scipy.stats import kurtosis, skew
from collections import deque
from copy import copy
from statistics import mode, StatisticsError
import re
import argparse
import numpy as np

fieldBlacklist = ['#Time', 'Time_usec', 'ProducerName', 'component_id', 'job_id']
timeLabel = '#Time'
taskLabel = '#Benchmark'
faultLabel = '#Fault'
perCoreLabels = ['per_core_', '#']
label_separator = CSVWriter.L1_DELIMITER_CHAR
percentiles = [0, 5, 25, 50, 75, 95, 100]
percentileLabel = '_perc'

allowedMetricsLUT = {}


def computeDerivatives(oldEntry, newEntry):
    diff = {k: v - oldEntry[k] for k, v in newEntry.items()}
    return diff


def getStatistics(myData, metricName):
    stats = {}
    stats[metricName + '_avg'] = np.asscalar(np.average(myData))
    stats[metricName + '_std'] = np.asscalar(np.std(myData))
    stats[metricName + '_skew'] = skew(myData)
    stats[metricName + '_kurt'] = kurtosis(myData)
    percs = np.percentile(myData, percentiles)
    for ind, p in enumerate(percs):
        if ind == 0:
            stats[metricName + '_min'] = p
        elif ind == len(percs) - 1:
            stats[metricName + '_max'] = p
        else:
            stats[metricName + percentileLabel + str(percentiles[ind])] = p
    return stats


def isMetricAllowed(k, regexp):
    if k not in allowedMetricsLUT.keys():
        allowedMetricsLUT[k] = k not in fieldBlacklist and (not any(l in k for l in perCoreLabels) or regexp.search(k) if regexp is not None else True)
    return allowedMetricsLUT[k]


def updateAndFilter(dest, src, regexp=None):
    goodVals = {k: float(v) for k, v in src.items() if isMetricAllowed(k, regexp)}
    dest.update(goodVals)
    return dest


def readLabelsasDict(path, key):
    infile = open(path, 'r')
    reader = DictReader(infile, delimiter=CSVWriter.DELIMITER_CHAR)
    myDict = {}
    try:
        entry = next(reader)
    except (StopIteration, IOError):
        infile.close()
        return None
    while entry is not None:
        entryKey = entry[key]
        entry.pop(key)
        myDict[int(entryKey)] = entry
        try:
            entry = next(reader)
        except (StopIteration, IOError):
            entry = None
    infile.close()
    return myDict


def filterTaskLabels(label, core):
    if label == CSVWriter.NONE_VALUE:
        return label
    labelGroup = label.split(label_separator)
    finalLabelGroup = []
    for label in labelGroup:
        labelCores = label.split('_')[1]
        if core is None or core in labelCores.split(','):
            finalLabelGroup.append(label.split('_')[0])
    return ','.join(finalLabelGroup) if len(finalLabelGroup) > 0 else CSVWriter.NONE_VALUE


def buildFeatures(inpaths, labelfile, out, window=60, step=1, core=None):
    infiles = {}
    readers = {}
    regularexp = re.compile("[^0-9]" + core) if core is not None else None
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
    labelDict = readLabelsasDict(labelfile, timeLabel)
    if labelDict is None:
        return None
    while True:
        # With this approach metrics coming from different files MAY slightly dis-align over time, even if they start
        # from the same timestamp and have the same step
        try:
            entry = next(pilotReader)
        except (StopIteration, IOError):
            break
        currTimestamp = int(entry[timeLabel].split('.')[0])
        lastEntry = updateAndFilter(lastEntry, entry, regularexp)

        for reader in readers.values():
            try:
                entry = next(reader)
            except (StopIteration, IOError):
                continue
            lastEntry = updateAndFilter(lastEntry, entry, regularexp)
        currDerivative = computeDerivatives(entriesQueue[0][1], lastEntry) if len(entriesQueue) > 0 else None
        try:
            currFault = labelDict[currTimestamp][faultLabel]
            # filterTaskLabels(labelDict[currTimestamp][faultLabel], core)
        except KeyError:
            currFault = 'None'
        try:
            currBenchmark = labelDict[currTimestamp][taskLabel]
            # filterTaskLabels(labelDict[currTimestamp][taskLabel], core)
        except KeyError:
            currBenchmark = 'None'
        entriesQueue.appendleft((currTimestamp, copy(lastEntry), currDerivative, currFault, currBenchmark))
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
            feature[timeLabel] = int(np.asscalar(np.average([en[0] for en in entriesQueue])))
            try:
                faultL = [en[3] for en in entriesQueue]
                feature[faultLabel] = mode(faultL)
            except StatisticsError:
                feature[faultLabel] = max(set(faultL), key=faultL.count)
            try:
                taskL = [en[4] for en in entriesQueue]
                feature[taskLabel] = mode(taskL)
            except StatisticsError:
                feature[taskLabel] = max(set(taskL), key=taskL.count)
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
    parser = argparse.ArgumentParser(description="Fin-J CSV Features Builder Tool. \n"
                                                 "PAY ATTENTION: this currently works only with non-overlapping tasks")
    parser.add_argument("-f", action="store", dest="sources", type=str, default=None,
                        help="Path to the CSV files to be analyzed, separated by comma.")
    parser.add_argument("-l", action="store", dest="labelfile", type=str, default=None,
                        help="Path to the CSV file containing the labels, generated with log_to_labels.")
    parser.add_argument("-w", action="store", dest="window", type=int, default=60,
                        help="Length of the aggregation window, in samples.")
    parser.add_argument("-s", action="store", dest="step", type=int, default=10,
                        help="Step between adjacent features, in samples.")
    parser.add_argument("-o", action="store", dest="out", type=str, default="out.csv",
                        help="Path to the output file.")
    parser.add_argument("-c", action="store", dest="core", type=str, default=None,
                        help="Selects a single core ID for which per-core metrics must be used.")
    args = parser.parse_args()
    sources = args.sources.split(',') if args.sources is not None else None
    if sources is None or args.labelfile is None:
        print("You must supply at least one path to a CSV file that must be analyzed!")
        exit(-1)
    if args.window < 1:
        args.window = 1
    if args.step < 1:
        args. step = 1
    buildFeatures(sources, args.labelfile, args.out, args.window, args.step, args.core)
    exit(0)
