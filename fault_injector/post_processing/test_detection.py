from csv import DictReader
from fault_injector.post_processing.constants import faultLabel, benchmarkLabel, timeLabel, mixedLabel
from fault_injector.post_processing.constants import derivLabel, perCoreLabels, coreRange
from fault_injector.post_processing.build_features import filterTaskLabels
from sklearn.model_selection import cross_validate
from sklearn.ensemble import RandomForestClassifier, AdaBoostClassifier
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import make_scorer, f1_score
from sklearn.exceptions import NotFittedError
from fault_injector.util.misc import TASKNAME_SEPARATOR
from fault_injector.io.writer import CSVWriter
from random import randint
import numpy as np
import argparse, re
import warnings


# List of classifiers to be used for detection
clfList = [RandomForestClassifier(n_estimators=50),
           AdaBoostClassifier(n_estimators=50),
           SVC(kernel='rbf'),
           DecisionTreeClassifier(criterion='gini'),
           MLPClassifier(activation='relu', hidden_layer_sizes=(1000, 1000))]


def featureTest(entry, label, noMix):
    """
    Boolean test for the validity of feature vectors.

    Returns False if the feature vector corresponds to a fault programs that is "busy-only", and the system is currently
    idling. It also returns False if ambiguous feature vectors are banned from use, and the feature vector is ambiguous

    :param entry: The metrics dictionary for the feature vector
    :param label: The label for the feature vector
    :param noMix: True if ambiguous feature vectors cannot be used, False otherwise
    :return: True if the feature vector can be used, False otherwise
    """
    #return (label not in busyFaults or entry[benchmarkLabel] != CSVWriter.NONE_VALUE) and not (noMix and float(entry[mixedLabel]) > 0.5)
    return not (noMix and float(entry[mixedLabel]) > 0.5)


def loadFeatures(inpath, maxFeatures=-1, noMix=False, discardDerivs=False, splitFeatures=False, splitSets=False):
    """
    Given the filepath of an input CSV feature file, this function reads all features from the file and stores them in
    a Numpy matrix suitable for use with SciKit classifiers. It returns the feature matrix and the list of labels for
    each feature.

    :param inpath: path to the input CSV features file, or list of paths
    :param maxFeatures: Maximum number of features to be read
    :param noMix: If True, all feature vectors belonging to ambiguous system states (#mixed != 0) are discarded
    :param discardDerivs: If True, all metrics related to first-order derivatives are removed from feature vectors
    :return: A Numpy matrix in which each row is a feature vector, and a list of labels
    :param splitFeatures: if True, the algorithm supposes that per-core metrics related to multiple cores are present
        in the data, and will thus proceed to split each feature vector for each single core
    :param splitSets: if True, and if splitFeatures is True as well, the feature vectors from different cores are
        returned as separate feature matrix / label list pairs
    """
    fieldBlacklist = [timeLabel, faultLabel, benchmarkLabel, mixedLabel]
    infiles = {}
    readers = {}
    readers_to_pop = []

    for p in inpath:
        infiles[p] = open(p, 'r')
        readers[p] = DictReader(infiles[p])

    if splitFeatures and splitSets:
        featureMatrix = {str(i): [] for i in range(coreRange[0], coreRange[1] + 1)}
        labelMatrix = {str(i): [] for i in range(coreRange[0], coreRange[1] + 1)}
    else:
        featureMatrix = []
        labelMatrix = []
    sortedKeys = None
    featureDict = None
    counter = 0
    while readers and (maxFeatures == -1 or counter < maxFeatures):
        if len(readers_to_pop) > 0:
            for p in readers_to_pop:
                infiles[p].close()
                infiles.pop(p)
                readers.pop(p)
            readers_to_pop.clear()
        for p, r in readers.items():
            try:
                entry = next(r)
            except (StopIteration, IOError):
                readers_to_pop.append(p)
                continue
            if sortedKeys is None:
                sortedKeys = sorted([k for k in entry.keys() if k not in fieldBlacklist and not (discardDerivs and derivLabel in k)])
                if splitFeatures:
                    sortedKeys, featureDict = computeSplitFeatures(sortedKeys)

            if not splitFeatures:
                featureLabel = entry[faultLabel].rsplit(TASKNAME_SEPARATOR, 1)[0]
                if featureTest(entry, featureLabel, noMix):
                    featureMatrix.append([float(entry[k]) for k in sortedKeys])
                    labelMatrix.append(featureLabel)
            else:
                for c in featureDict.keys():
                    busyGlobal = entry[benchmarkLabel] != CSVWriter.NONE_VALUE
                    busyLocal = filterTaskLabels(entry[benchmarkLabel], c, False) != CSVWriter.NONE_VALUE
                    percoreFeatureLabel = filterTaskLabels(entry[faultLabel], c, True, busy=(busyGlobal, busyLocal))
                    if featureTest(entry, percoreFeatureLabel, noMix):
                        if not splitSets:
                            featureMatrix.append([float(entry[k]) for k in featureDict[c]])
                            labelMatrix.append(percoreFeatureLabel)
                        else:
                            featureMatrix[c].append([float(entry[k]) for k in featureDict[c]])
                            labelMatrix[c].append(percoreFeatureLabel)
            counter += 1

    for f in infiles.values():
        f.close()
    if splitFeatures and splitSets:
        labelMatrix = {k: np.array(v, dtype=str) for k, v in labelMatrix.items()}
        featureMatrix = {k: np.array(v, dtype=np.float64) for k, v in featureMatrix.items()}
    else:
        labelMatrix = {'None': np.array(labelMatrix, dtype=str)}
        featureMatrix = {'None': np.array(featureMatrix, dtype=np.float64)}
    return featureMatrix, labelMatrix, np.array(sortedKeys)


def computeSplitFeatures(sortedKeys):
    """
    This function takes as input a list of metric labels, and splits it in N different sets, each containing labels
    for system-wide metrics and also metrics specific for the i-th core

    :param sortedKeys: The list of input labels
    :return: A tuple containing two elements. The first is the list of final labels, containing the names of all metrics
        stripped of core number information, for display purposes. The second is instead a dictionary with N entries,
        one for each core in the system, each containing the list of metric keys that should be used for that core,
        and that are mapped to the first list of the output tuple
    """
    globalKeys = [k for k in sortedKeys if not any(l in k for l in perCoreLabels)]
    localKeys = [k for k in sortedKeys if k not in globalKeys]
    featureDict = {}
    for c in range(coreRange[0], coreRange[1] + 1):
        regularexp = re.compile("[^0-9]" + str(c) + "_")
        percoreFeatures = [key for key in localKeys if regularexp.search(key)]
        featureDict[str(c)] = percoreFeatures + globalKeys
    metricLabels = [key.replace(str(coreRange[1]), '') for key in featureDict[str(coreRange[1])]]
    return metricLabels, featureDict


def getScorerObjects(labels):
    """
    Creates a dictionary of SciKit scorer objects. Each object considers features from a specific class out of those
    given as input, and the metric used here is the F-Score

    :param labels: The list of class labels
    :return: A list of Scikit scorer objects
    """
    labelSet = set(labels)
    scorers = {}
    for label in labelSet:
        scorers[label] = make_scorer(f1_score, average=None, labels=[label])
    scorers['weighted'] = make_scorer(f1_score, average='weighted')
    return scorers


def shuffle(features, labels):
    """
    Performs shuffling over the input feature vector matrix and list of labels

    :param features: A matrix containing feature vectors in each row
    :param labels: A list of labels associated to each feature vector
    """
    for k in features.keys():
        featureSub = features[k]
        labelSub = labels[k]
        numSwaps = int(len(labelSub) / 2)
        for i in range(numSwaps):
            idx1 = randint(0, len(labelSub) - 1)
            idx2 = randint(0, len(labelSub) - 1)
            tmpLabel = labelSub[idx2]
            labelSub[idx2] = labelSub[idx1]
            labelSub[idx1] = tmpLabel
            featureSub[[idx1, idx2], :] = featureSub[[idx2, idx1], :]


# This script takes as input a CSV file containing features suitable for machine learning classification. It will test
# the file over a set of classifiers and report the obtained accuracy
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Fin-J Fault Detection Test Tool")
    parser.add_argument("-f", action="store", dest="sources", type=str, default=None,
                        help="Path to the CSV features file to be used. You can also supply multiple comma-separated "
                             "files: in that case, one entry is read from each file in round-robin fashion, and they "
                             "must contain an identical set of metrics.")
    parser.add_argument("-m", action="store", dest="maxf", type=int, default=-1,
                        help="Maximum number of feature vectors to be processed")
    parser.add_argument("-p", action="store", dest="impMetrics", type=int, default=0,
                        help="Number of most important metrics to print when using supported classifiers.")
    parser.add_argument("-n", action="store_true", dest="noMix",
                        help="Use only feature vectors corresponding to non-ambiguous states.")
    parser.add_argument("-d", action="store_true", dest="discardDerivs",
                        help="Discard metrics related to first-order derivatives in feature vectors.")
    parser.add_argument("-c", action="store_true", dest="splitFeatures",
                        help="Instructs the algorithm that feature vectors include information from multiple cores and"
                             "must thus be split in separate feature vectors.")
    parser.add_argument("-C", action="store_true", dest="splitFeaturesAlt",
                        help="Like the -c option. In addition, the feature vectors from different cores are fed to"
                             "separate classifiers, and not to the same classifier.")
    parser.add_argument("-s", action="store_true", dest="shuffle",
                        help="Shuffles the order of feature vectors before performing classification.")
    args = parser.parse_args()
    sources = args.sources.split(',') if args.sources is not None else None
    if sources is None:
        print("You must supply the path to the features file that must be used!")
        exit(-1)
    if args.maxf < -1 or args.maxf == 0:
        args.maxf = -1
    print('---------- FINJ CROSS-VALIDATION TOOL ----------')
    print('- Input source: %s' % args.sources)
    if args.noMix:
        print('- Ambiguous feature vectors are being discarded.')
    if args.discardDerivs:
        print('- First-order derivatives are being discarded from feature vectors.')
    print('- Loading features...')
    features, labels, metricKeys = loadFeatures(sources, maxFeatures=args.maxf, noMix=args.noMix,
                                                discardDerivs=args.discardDerivs, splitSets=args.splitFeaturesAlt,
                                                splitFeatures=args.splitFeatures or args.splitFeaturesAlt)
    if args.shuffle:
        print('- The order of feature vectors will be shuffled.')
        shuffle(features, labels)
    if args.splitFeatures:
        print('- Feature vectors will be split for different cores.')
    if args.splitFeaturesAlt:
        print('- Feature vectors will be split for different cores and fed to separate classifiers.')
    print('- Feature vector length is %s...' % len(list(features.values())[0][0, :]))
    print('- Number of feature vectors is %s...' % len(list(features.values())[0][:, 0]))
    print('- Performing cross-validation...')
    print('---------------')
    warnings.filterwarnings('ignore')
    # After loading the features, we perform cross-validation over the list of classifiers defined above, and print
    # the results.
    for k in features.keys():
        if k != 'None':
            print('--------------- Core %s ---------------' % k)
        featureSub = features[k]
        labelSub = labels[k]
        for clf in clfList:
            scorers = getScorerObjects(labelSub)
            scores = cross_validate(clf, featureSub, labelSub, cv=5, scoring=scorers, n_jobs=-1)
            print('- Classifier: %s' % clf.__class__.__name__)
            mean = scores['test_weighted'].mean()
            confidence = scores['test_weighted'].std() * 1.96 / np.sqrt(len(scores['test_weighted']))
            print('- Global F-Score : %s (+/- %s)' % (mean, confidence))
            for k, v in scores.items():
                if 'test_' in k and k != 'test_weighted':
                    mean = scores[k].mean()
                    confidence = scores[k].std() * 1.96 / np.sqrt(len(scores[k]))
                    print('---- %s F-Score : %s (+/- %s)' % (k.split('_')[1], mean, confidence))
            # Hackish way to detect if the current classifier supports feature importances
            supportsImportances = False
            try:
                importances = clf.feature_importances_
            except NotFittedError:
                supportsImportances = True
            except AttributeError:
                supportsImportances = False
            if supportsImportances and args.impMetrics > 0:
                # We fit the random forest classifier just to extract the information regarding
                # which are the most important metrics in the features
                clf.fit(featureSub, labelSub)
                importances = clf.feature_importances_
                indices = np.argsort(importances)[::-1]
                print('- Most important features:')
                for idx in range(args.impMetrics if args.impMetrics < len(indices) else len(indices)):
                    metric = indices[idx]
                    print('---- %s: %s' % (metricKeys[metric], importances[metric]))
            print('---------------')
    exit(0)
