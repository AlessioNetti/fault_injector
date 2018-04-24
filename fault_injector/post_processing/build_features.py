from fault_injector.io.writer import CSVWriter
from fault_injector.post_processing.constants import metricsBlacklist, faultLabel, timeLabel, benchmarkLabel
from fault_injector.post_processing.constants import perCoreLabels, localFaults, busyLabel, mixedLabel
from csv import DictWriter, DictReader
from scipy.stats import kurtosis, skew
from collections import deque
from copy import deepcopy
from statistics import mode, StatisticsError
import re
import argparse
import numpy as np

# Percentile values to be used for features
percentiles = [0, 5, 25, 50, 75, 95, 100]
# Internal variable used in the algorithm, do not change
allowedMetricsLUT = {}


# Computes first-order derivatives between two corresponding sets of metrics
def computeDerivatives(oldEntry, newEntry):
    diff = {k: v - oldEntry[k] for k, v in newEntry.items()}
    return diff

# Given a list of data, returns a dictionary of statistical features for such data, with each entry named according
# to an input label
def getStatistics(myData, metricName):
    percentileLabel = '_perc'
    stats = {}
    stats[metricName + '_avg'] = np.asscalar(np.average(myData))
    stats[metricName + '_std'] = np.asscalar(np.std(myData))
    stats[metricName + '_skew'] = skew(myData)
    stats[metricName + '_kurt'] = kurtosis(myData)
    percs = np.percentile(myData, percentiles)
    for ind, p in enumerate(percs):
        # Percentiles 0 and 100 are respectively the minimum and the maximum in the data
        if ind == 0:
            stats[metricName + '_min'] = p
        elif ind == len(percs) - 1:
            stats[metricName + '_max'] = p
        else:
            stats[metricName + percentileLabel + str(percentiles[ind])] = p
    return stats

# Returns True if the given metric name is allowed for use in the feature, and False otherwise.
# A metric is NOT allowed if it belongs to the metrics blacklist (defined in the constants file), or if it belongs
# to a core that is not the one we are building metrics for
def isMetricAllowed(k, regexp):
    if k not in allowedMetricsLUT.keys():
        allowedMetricsLUT[k] = k not in metricsBlacklist and (not any(l in k for l in perCoreLabels) or regexp.search(k) if regexp is not None else True)
    return allowedMetricsLUT[k]


# Updates a features dictionary with entries from a second, new dictionary, by filtering out those that are not allowed
def updateAndFilter(dest, src, regexp=None):
    goodVals = {k: float(v) for k, v in src.items() if isMetricAllowed(k, regexp)}
    dest.update(goodVals)
    return dest

# Reads a CSV file containing benchmark/fault labels for each timestamp (i.e. as produced by log_to_labels) and stores
# it in a dictionary whose keys are the timestamps
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

# Given a string containing a list of task/fault labels together with the cores they are running on, and a core ID,
# this function returns the string containing the sublist of tasks that belong to the specific core
# By default a task running on a different core than the input one is discarded: the only exceptions are with faults
# that are considered "global", such as a memory leak, that affect the entire system regardless of the core they
# are running on. This is regulated by the localFaults list in the constants file
def filterTaskLabels(label, core, isFault=False):
    if label == CSVWriter.NONE_VALUE:
        return label
    labelGroup = label.split(CSVWriter.L1_DELIMITER_CHAR)
    finalLabel = None
    for label in labelGroup:
        taskname, labelCores = label.split('_')
        if core is None or core in labelCores.split(',') or (isFault and taskname not in localFaults):
            if finalLabel is None:
                finalLabel = taskname
            else:
                print('There may be multiple tasks running at the same time in the workload. This is not allowed as'
                      ' it would lead to multiple labels for each feature.')
    return finalLabel if finalLabel is not None else CSVWriter.NONE_VALUE


# Given the queue of entries as defined in buildFeatures, this function returns True if its state is non-ambiguous.
# The state is considered ambiguous if in the queue there are entries with different task labels (for example when
# a fault or benchmark finished or has just started) which users may want to filter out to increase the quality
# of the features
def isStateAmbiguous(enQueue):
    faultEquality = all(enQueue[0][3] == en[3] for en in enQueue)
    benchmarkEquality = all(enQueue[0][4] == en[4] for en in enQueue)
    return not (faultEquality and benchmarkEquality)


# Given a list of paths corresponding to CSV files containing metrics to use, a file containing labels for each
# timestamp, and a set of parameters, this script build an output CSV file containing features built from the input
# metrics
def buildFeatures(inpaths, labelfile, out, window=60, step=10, core=None, useDerivatives=False):
    infiles = {}
    readers = {}
    # This regular expression identifies metrics that are related to the core we are analyzing
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

    # Using a deque to store entries for efficiency
    entriesQueue = deque()
    currStep = 0
    lastEntry = {}
    outfile = None
    writer = None
    # Reading the labels file and storing it in a dictionary
    labelDict = readLabelsasDict(labelfile, timeLabel)
    if labelDict is None:
        return None
    while True:
        # With this approach metrics coming from different files MAY slightly dis-align over time, even if they start
        # from the same timestamp and have the same step
        # We read one entry from the "main" metrics CSV file, and then from all the others; then we store and merge
        # their items in a single dictionary, which is kept across iterations
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

        # We compute the label of the benchmark currently running on this core, if any
        try:
            currBenchmark = filterTaskLabels(labelDict[currTimestamp][benchmarkLabel], core, isFault=False)
        except KeyError:
            currBenchmark = CSVWriter.NONE_VALUE
        lastEntry[busyLabel] = 0.0 if currBenchmark == CSVWriter.NONE_VALUE else 1.0

        # We compute the label of the fault currently running on this core, if any
        # This must be performed here and not later, because otherwise having potentially multiple labels would
        # interfere with the aggregation process
        try:
            currFault = filterTaskLabels(labelDict[currTimestamp][faultLabel], core, isFault=True)
        except KeyError:
            currFault = CSVWriter.NONE_VALUE

        # Having processed the current entry, we compute its first-order derivative
        currDerivative = computeDerivatives(entriesQueue[0][1], lastEntry) if len(entriesQueue) > 0 else None
        # We then insert the newly processed entry, together with its labels and derivative, into the deque
        entriesQueue.appendleft((currTimestamp, deepcopy(lastEntry), currDerivative, currFault, currBenchmark))
        # The deque has a maximum length corresponding to the aggregation window
        if len(entriesQueue) > window:
            entriesQueue.pop()
        currStep += 1
        # If we have analyzed a sufficient number of entries and reached the required step, we synthesize a new feature
        if currStep > step and len(entriesQueue) >= window:
            currStep = 0
            feature = {}
            for k in lastEntry.keys():
                # Processing statistical features for all metrics in all entries in the queue
                feature.update(getStatistics([en[1][k] for en in entriesQueue], k))
                # Processing statistical features for first-order derivative entries in the queue
                if useDerivatives:
                    feature.update(getStatistics([en[2][k] for en in entriesQueue if en[2] is not None], k + '_der'))
            feature[timeLabel] = int(np.asscalar(np.average([en[0] for en in entriesQueue])))
            # If the feature contains multiple states (i.e. tasks) we signal it in a field
            feature[mixedLabel] = 1.0 if isStateAmbiguous(entriesQueue) else 0.0
            # The benchmark/fault labels of the feature are given by the mode of the respective fields
            try:
                taskL = [en[4] for en in entriesQueue]
                feature[benchmarkLabel] = mode(taskL)
            except StatisticsError:
                feature[benchmarkLabel] = max(set(taskL), key=taskL.count)
            try:
                faultL = [en[3] for en in entriesQueue]
                feature[faultLabel] = mode(faultL)
            except StatisticsError:
                feature[faultLabel] = max(set(faultL), key=faultL.count)
            # The feature is written to the output file
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
    parser.add_argument("-d", action="store_true", dest="useDeriv",
                        help="Include first-order derivatives as well in feature generation.")
    args = parser.parse_args()
    sources = args.sources.split(',') if args.sources is not None else None
    if sources is None or args.labelfile is None:
        print("You must supply at least one path to a CSV file that must be analyzed!")
        exit(-1)
    if args.window < 1:
        args.window = 1
    if args.step < 1:
        args. step = 1
    buildFeatures(sources, args.labelfile, args.out, args.window, args.step, args.core, args.useDeriv)
    exit(0)
