from csv import DictReader
from fault_injector.post_processing.constants import faultLabel, benchmarkLabel, timeLabel, mixedLabel
from fault_injector.post_processing.constants import derivLabel
from fault_injector.post_processing.test_detection import featureTest, shuffle
from sklearn.ensemble import RandomForestClassifier, AdaBoostClassifier
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import f1_score
from fault_injector.util.misc import TASKNAME_SEPARATOR
import numpy as np
import argparse
import warnings


# List of classifiers to be used for detection
clfList = [RandomForestClassifier(n_estimators=50),
           AdaBoostClassifier(n_estimators=50),
           SVC(kernel='rbf'),
           DecisionTreeClassifier(criterion='gini'),
           MLPClassifier(activation='relu', hidden_layer_sizes=(1000, 1000))]


def loadFeatures(inpath, maxFeatures=-1, noMix=False, discardDerivs=False):
    """
    Given the filepath of an input CSV feature file, this function reads all features from the file and stores them in
    a Numpy matrix suitable for use with SciKit classifiers. It returns the feature matrix and the list of labels for
    each feature.

    :param inpath: path to the input CSV features file, or list of paths
    :param maxFeatures: Maximum number of features to be read
    :param noMix: If True, all feature vectors belonging to ambiguous system states (#mixed != 0) are discarded
    :param discardDerivs: If True, all metrics related to first-order derivatives are removed from feature vectors
    :return: A Numpy matrix in which each row is a feature vector, and a list of labels
    """
    fieldBlacklist = [timeLabel, faultLabel, benchmarkLabel, mixedLabel]
    infiles = {}
    readers = {}
    readers_to_pop = []

    for p in inpath:
        infiles[p] = open(p, 'r')
        readers[p] = DictReader(infiles[p])

    sortedKeys = None
    featureMatrix = []
    labelMatrix = []
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

            featureLabel = entry[faultLabel].rsplit(TASKNAME_SEPARATOR, 1)[0]
            if featureTest(entry, featureLabel, noMix):
                featureMatrix.append([float(entry[k]) for k in sortedKeys])
                labelMatrix.append(featureLabel)

            counter += 1

    for f in infiles.values():
        f.close()
    labelMatrix = {'None': np.array(labelMatrix, dtype=str)}
    featureMatrix = {'None': np.array(featureMatrix, dtype=np.float64)}
    return featureMatrix, labelMatrix, np.array(sortedKeys)


# This script takes as input a CSV file containing features suitable for machine learning classification. It will test
# the file over a set of classifiers and report the obtained accuracy
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Fin-J Fault Detection Test Tool - ALTERNATIVE VERSION")
    parser.add_argument("-f", action="store", dest="sources", type=str, default=None,
                        help="Path to the CSV features file to be used for training. You can also supply multiple "
                             "comma-separated files: in that case, one entry is read from each file in round-robin "
                             "fashion, and they must contain an identical set of metrics.")
    parser.add_argument("-t", action="store", dest="target", type=str, default=None,
                        help="Path to the target CSV features file to be used for testing only.")
    parser.add_argument("-m", action="store", dest="maxf", type=int, default=-1,
                        help="Maximum number of feature vectors to be processed")
    parser.add_argument("-p", action="store", dest="impMetrics", type=int, default=0,
                        help="Number of most important metrics to print when using supported classifiers.")
    parser.add_argument("-n", action="store_true", dest="noMix",
                        help="Use only feature vectors corresponding to non-ambiguous states.")
    parser.add_argument("-d", action="store_true", dest="discardDerivs",
                        help="Discard metrics related to first-order derivatives in feature vectors.")
    parser.add_argument("-s", action="store_true", dest="shuffle",
                        help="Shuffles the order of feature vectors before performing classification.")
    args = parser.parse_args()
    sources = args.sources.split(',') if args.sources is not None else None
    if sources is None:
        print("You must supply the path to the features file that must be used!")
        exit(-1)
    target = args.target.split(',') if args.target is not None else None
    if target is None:
        print("You must supply the path to the target features file that must be used!")
        exit(-1)
    if args.maxf < -1 or args.maxf == 0:
        args.maxf = -1
    print('---------- FINJ CROSS-VALIDATION TOOL - ALTERNATIVE VERSION ----------')
    print('- Input source: %s' % args.sources)
    print('- Target file: %s' % args.target)
    if args.noMix:
        print('- Ambiguous feature vectors are being discarded.')
    if args.discardDerivs:
        print('- First-order derivatives are being discarded from feature vectors.')
    print('- Loading features...')
    features, labels, metricKeys = loadFeatures(sources, maxFeatures=args.maxf, noMix=args.noMix,
                                                discardDerivs=args.discardDerivs)
    tFeatures, tLabels, tMetricKeys = loadFeatures(target, maxFeatures=args.maxf, noMix=args.noMix,
                                                discardDerivs=args.discardDerivs)
    if args.shuffle:
        print('- The order of feature vectors will be shuffled.')
        shuffle(features, labels)
        shuffle(tFeatures, tLabels)
    print('- Feature vector length is %s...' % len(list(features.values())[0][0, :]))
    print('- Number of feature vectors is %s...' % (len(list(features.values())[0][:, 0]) + len(list(tFeatures.values())[0][:, 0])))
    print('- Performing cross-validation...')
    print('---------------')
    warnings.filterwarnings('ignore')
    # After loading the features, we perform cross-validation over the list of classifiers defined above, and print
    # the results.
    featureSub = features['None']
    labelSub = labels['None']
    tFeatureSub = tFeatures['None']
    tLabelSub = tLabels['None']
    labelSet = set(labelSub)
    for clf in clfList:
        clf.fit(featureSub, labelSub)
        tPred = clf.predict(tFeatureSub)
        print('- Classifier: %s' % clf.__class__.__name__)
        globalScore = f1_score(tLabelSub, tPred, average='weighted')
        print('- Global F-Score : %s' % globalScore)
        for k in labelSet:
            classScore = f1_score(tLabelSub, tPred, average=None, labels=[k])
            print('---- %s F-Score : %s' % (k, classScore))
        print('---------------')
    exit(0)
