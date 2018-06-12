from fault_injector.io.writer import CSVWriter
from fault_injector.post_processing.constants import metricsBlacklist, faultLabel, timeLabel, benchmarkLabel
from fault_injector.post_processing.constants import perCoreLabels, localFaults, busyLabel, mixedLabel, derivLabel
from fault_injector.post_processing.constants import coreRange, localBusyFaults, globalBusyFaults
from fault_injector.util.misc import TASKNAME_SEPARATOR, VALUE_ALL_CORES
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


def findMaxima(inpaths, core):
    """
    Given a list of paths to CSV metric files, returns a dictionary containing the global maximum for each metric key

    :param inpaths: A list of CSV file paths containing system performance metrics
    :param regexp: If not None, must be a string representing the ID of the analyzed core
    :return: A dictionary of maximal values for each metric key
    """
    maxima = {}
    readers = {}
    infiles = {}
    for ind, p in enumerate(inpaths):
            infile = open(p, 'r')
            infiles[p] = infile
            readers[p] = DictReader(infile)

    for p, reader in readers.items():
        while True:
            try:
                entry = next(reader)
            except (StopIteration, IOError):
                infiles[p].close()
                infiles.pop(p)
                break
            for k, v in entry.items():
                if isMetricAllowed(k, core):
                    value = float(v)
                    if k not in maxima or value > maxima[k]:
                        maxima[k] = value
    return maxima


def computeDerivatives(oldEntry, newEntry):
    """
    Computes first-order derivatives between two corresponding sets of metrics

    :param oldEntry: Dictionary of metrics at time t - 1
    :param newEntry: Dictionary of metrics at time t
    :return: Dictionary of first-order derivatives
    """
    diff = {k: v - oldEntry[k] for k, v in newEntry.items()}
    return diff


def getStatistics(myData, metricName):
    """
    Given a list of data, returns a dictionary of statistical features for such data, with each entry named according
    to an input label. Considered features are: avg, std, min, max, skewness, kurtosis, (5, 25, 50, 75, 95)th percentiles

    :param myData: A list containing numerical data
    :param metricName: String, containing the name of the metric being analysed
    :return: A dictionary of statistical features for the input data
    """
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


def isMetricAllowed(k, core):
    """
    Returns True if the given metric name is allowed for use in the feature, and False otherwise.
    A metric is NOT allowed if it belongs to the metrics blacklist (defined in the constants file), or if it belongs
    to a core that is not the one we are building metrics for

    :param k: key of a given metric
    :param core: If not None, must be a string representing the ID of the analyzed core
    :return: True if metric k is allowed, False otherwise
    """
    if k not in allowedMetricsLUT.keys():
        # Checking if the metric is per-core
        if any(l in k for l in perCoreLabels):
            if core is not None:
                # If we supplied a core for analysis, we check that the metric corresponds to that core
                regularexp = re.compile("[^0-9]" + core + "$")
                belongsToCore = True if regularexp.search(k) is not None else False
            else:
                # Otherwise, we check over all core IDs defined in coreRange for a match
                belongsToCore = False
                for c in range(coreRange[0], coreRange[1] + 1):
                    regularexp = re.compile("[^0-9]" + str(c) + "$")
                    belongsToCore = True if regularexp.search(k) is not None else False
                    if belongsToCore:
                        break
        else:
            # If the metric is not per-core, there is no check to perform
            belongsToCore = True
        allowedMetricsLUT[k] = k not in metricsBlacklist and belongsToCore
    return allowedMetricsLUT[k]


def updateAndFilter(dest, src, core=None, maxima=None):
    """
    Updates a features dictionary with entries from a second, new dictionary, by filtering out those that are not allowed

    :param dest: Dictionary that must be updated with new values
    :param src: Dictionary containing new values that must be integrated in the old dictionary
    :param core: If not None, must be a string representing the ID of the analyzed core
    :param maxima: If not None, must be a dictionary containing the maximal value for each metric for normalization
    :return: The dest dictionary updated with new values from src
    """
    if maxima is None:
        goodVals = {k: float(v) for k, v in src.items() if isMetricAllowed(k, core)}
    else:
        goodVals = {k: float(v) / (maxima[k] if maxima[k] != 0 else 1) for k, v in src.items() if isMetricAllowed(k, core)}
    dest.update(goodVals)
    return dest


def readLabelsasDict(path, key):
    """
    Reads a CSV file containing benchmark/fault labels for each timestamp (i.e. as produced by log_to_labels) and stores
    it in a dictionary whose keys are the timestamps

    :param path: Path to the CSV labels file
    :param key: The name of the metric to be used as label for each timestamp
    :return: A dictionary of timestamp keys to label values
    """
    infile = open(path, 'r')
    reader = DictReader(infile, delimiter=CSVWriter.DELIMITER_CHAR)
    myDict = {}
    try:
        entry = next(reader)
    except (StopIteration, IOError):
        infile.close()
        return None
    while entry is not None:
        entryKey = int(entry[key].split('.')[0])
        entry.pop(key)
        myDict[entryKey] = entry
        try:
            entry = next(reader)
        except (StopIteration, IOError):
            entry = None
    infile.close()
    return myDict


def filterTaskLabels(label, core=None, isFault=False, busy=(True, True)):
    """
    Given a string containing a list of task/fault labels together with the cores they are running on, and a core ID,
    this function returns the string containing the sublist of tasks that belong to the specific core
    By default a task running on a different core than the input one is discarded: the only exceptions are the following:
    1) No core was specified for analysis;
    2) The task was run on an undefined set of cores (NUMA policy disabled or set to all)
    3) The task is a "global" fault, which impacts the entire system regardless of the core it is run on

    In addition, fault tasks that are of the "busy" type (they require applications to be running in the system) will be
    discarded if the system is not busy at either the global or local level

    :param label: String containing task labels, separated by comma
    :param core: Number of the core being considered. If None, the analysis involves all cores
    :param isFault: True if the labels correspond to fault programs, False otherwise
    :param busy: A tuple of two booleans. The first element is True if there is one application running on the system
        as a whole, and the second is True if there is one application running on the specified core
    :return: A string containing the subset of task labels from the input that are valid for this analysis
    """
    if label == CSVWriter.NONE_VALUE:
        return label
    labelGroup = label.split(CSVWriter.L1_DELIMITER_CHAR)
    finalLabel = None
    for label in labelGroup:
        splitName = label.rsplit(TASKNAME_SEPARATOR, 1)
        taskname = splitName[0]
        labelCores = splitName[1] if len(splitName) == 2 else VALUE_ALL_CORES
        # Verifying the conditions for the validity of the label
        if not (core is None or labelCores == VALUE_ALL_CORES or core in labelCores.split(',') or (isFault and taskname not in localFaults)):
            continue
        # Verifying that the task is not a fault belonging to the busy-only class
        if core is not None and isFault and ((not busy[0] and taskname in globalBusyFaults) or (not busy[1] and taskname in localBusyFaults)):
            continue

        if finalLabel is None:
            # If a core was specified, we strip the core information from the label, as it is redundant
            # If no core was specified, the core information is kept for further post-processing
            finalLabel = label if core is None else taskname
        else:
            print('There may be multiple tasks running at the same time in the workload. This is not allowed as'
                  ' it would lead to multiple labels for each feature.')
    return finalLabel if finalLabel is not None else CSVWriter.NONE_VALUE


def isStateAmbiguous(enQueue):
    """
    Given the queue of entries as defined in buildFeatures, this function returns True if its state is non-ambiguous.
    The state is considered ambiguous if in the queue there are entries with different task labels (for example when
    a fault or benchmark finished or has just started) which users may want to filter out to increase the quality
    of the features

    :param enQueue: The queue containing data point tuples (timestamp, metrics, derivatives, faultlabels, tasklabels)
    :return: True if the considered state is ambiguous, False otherwise
    """
    faultEquality = all(enQueue[0][3] == en[3] for en in enQueue)
    benchmarkEquality = all(enQueue[0][4] == en[4] for en in enQueue)
    return not (faultEquality and benchmarkEquality)


def computeBusyMetrics(benchmarkLabel, core=None):
    """
    Computes a set of metrics that defines whether the system is busy at system and core levels, i.e. running a
    benchmark.

    :param benchmarkLabel: A string containing the set of comma-separated labels of tasks currently running on the
        system, each labeled with the set of cores it is executed on
    :param core: The core that must be used for analysis, if any, or None. If None, all cores will be considered and
        metrics will be computed for them
    :return: A tuple containing a label for this timepoint, corresponding to a currently running application, and a
        dictionary of "busy" metrics for the entire system and each core, if required
    """
    metricsDict = {}
    # This first metric is the GLOBAL busy metric, which is set to 1 if there is at least one application running on
    # the system
    metricsDict[busyLabel] = 0.0 if benchmarkLabel == CSVWriter.NONE_VALUE else 1.0
    currBenchmark = filterTaskLabels(benchmarkLabel, core, isFault=False)
    # Then we compute the per-core busy metrics
    if core is not None:
        metricsDict[perCoreLabels[0] + busyLabel + core] = 0.0 if currBenchmark == CSVWriter.NONE_VALUE else 1.0
    else:
        for c in range(coreRange[0], coreRange[1] + 1):
            percoreBenchmark = filterTaskLabels(benchmarkLabel, str(c), isFault=False)
            metricsDict[perCoreLabels[0] + busyLabel + str(c)] = 0.0 if percoreBenchmark == CSVWriter.NONE_VALUE else 1.0
    return currBenchmark, metricsDict


def buildFeatures(inpaths, labelfile, out, window=60, step=10, core=None, useDerivatives=False, recentLabel=False, normalize=False):
    """
    Given a list of paths corresponding to CSV files containing metrics to use, a file containing labels for each
    timestamp, and a set of parameters, this script build an output CSV file containing features built from the input
    metrics

    :param inpaths: Path to the input CSV files containing system performance metrics
    :param labelfile: Path to the CSV file containing labels for each single timestamp
    :param out: Path to the output features CSV file
    :param window: Length (in samples) of the aggregation window
    :param step: Step (in samples) between feature vectors
    :param core: Core to be considered for analysis. If supplied, only per-core metrics related to that core (on top
        of global metrics) will be considered, and only tasks running on that core will be used for labeling
    :param useDerivatives: If True, first-order derivatives will be computed for each metric as well, and included
        in feature vectors. This will double the size of feature vectors
    :param recentLabel: If True, each feature vector is labeled by using only the label of the most recent data point
        in the aggregation window. By default instead, the mode of all labels in the aggregation window is used
    :param normalize: If True, normalization is performed, by considering the global maxima for every metric
    """
    infiles = {}
    readers = {}
    # If normalization is enabled, we first search for the global maxima of each metric
    maxima = findMaxima(inpaths, core) if normalize else None
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
        lastEntry = updateAndFilter(lastEntry, entry, core, maxima)
        for reader in readers.values():
            try:
                entry = next(reader)
            except (StopIteration, IOError):
                continue
            lastEntry = updateAndFilter(lastEntry, entry, core, maxima)
        # We compute the label of the benchmark currently running on this core, if any
        try:
            currBenchmark, busyMetrics = computeBusyMetrics(labelDict[currTimestamp][benchmarkLabel], core)
        except KeyError:
            print('- Timestamp %s not found' % currTimestamp)
            currBenchmark = CSVWriter.NONE_VALUE
            busyMetrics = {}
        lastEntry = updateAndFilter(lastEntry, busyMetrics, None, None)
        # We compute the label of the fault currently running on this core, if any
        # This must be performed here and not later, because otherwise having potentially multiple labels would
        # interfere with the aggregation process
        try:
            busyGlobal = lastEntry[busyLabel] != 0.0
            busyLocal = True if core is None else lastEntry[perCoreLabels[0] + busyLabel + core] != 0.0
            currFault = filterTaskLabels(labelDict[currTimestamp][faultLabel], core, isFault=True, busy=(busyGlobal, busyLocal))
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
                    feature.update(getStatistics([en[2][k] for en in entriesQueue if en[2] is not None], k + derivLabel))
            feature[timeLabel] = int(np.asscalar(np.average([en[0] for en in entriesQueue])))
            # If the feature contains multiple states (i.e. tasks) we signal it in a field
            feature[mixedLabel] = 1.0 if isStateAmbiguous(entriesQueue) else 0.0
            # The benchmark/fault labels of the feature are given by the mode of the respective fields
            try:
                taskL = [en[4] for en in entriesQueue]
                feature[benchmarkLabel] = mode(taskL) if not recentLabel else taskL[0]
            except StatisticsError:
                feature[benchmarkLabel] = max(set(taskL), key=taskL.count)
            try:
                faultL = [en[3] for en in entriesQueue]
                feature[faultLabel] = mode(faultL) if not recentLabel else faultL[0]
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
    parser.add_argument("-r", action="store_true", dest="labelMode",
                        help="Instead of using the mode of single time points to create the feature vector labels, "
                             "use only the label of the most recent time point.")
    parser.add_argument("-n", action="store_true", dest="normalize",
                        help="Normalize all metrics before feature generation.")
    args = parser.parse_args()
    sources = args.sources.split(',') if args.sources is not None else None
    if sources is None or args.labelfile is None:
        print("You must supply at least one path to a CSV file that must be analyzed!")
        exit(-1)
    if args.window < 1:
        args.window = 1
    if args.step < 1:
        args. step = 1
    buildFeatures(sources, args.labelfile, args.out, args.window, args.step, args.core, args.useDeriv, args.labelMode, args.normalize)
    exit(0)
