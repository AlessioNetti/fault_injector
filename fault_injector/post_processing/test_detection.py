from csv import DictReader
from fault_injector.io.writer import CSVWriter
from fault_injector.post_processing.constants import faultLabel, benchmarkLabel, timeLabel, mixedLabel, busyFaults, derivLabel
from sklearn.model_selection import cross_validate
from sklearn.ensemble import RandomForestClassifier, AdaBoostClassifier
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import make_scorer, f1_score
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


# Given the filepath of an input CSV feature file, this function reads all features from the file and stores them in
# a Numpy matrix suitable for use with SciKit classifiers. It returns the feature matrix and the list of labels for
# each feature.
def loadFeatures(inpath, maxFeatures=-1, noMix=False, discardDerivs=False):
    fieldBlacklist = [timeLabel, faultLabel, benchmarkLabel, mixedLabel]
    infile = open(inpath, 'r')
    reader = DictReader(infile)

    try:
        entry = next(reader)
    except (StopIteration, IOError):
        infile.close()
        return None

    featureMatrix = []
    labelMatrix = []
    sortedKeys = None
    counter = 0
    while entry is not None and (maxFeatures == -1 or counter < maxFeatures):
        if sortedKeys is None:
            sortedKeys = sorted([k for k in entry.keys() if k not in fieldBlacklist and not (discardDerivs and derivLabel in k)])
        featureLabel = entry[faultLabel].rsplit(TASKNAME_SEPARATOR, 1)[0]
        if (featureLabel not in busyFaults or entry[benchmarkLabel] != CSVWriter.NONE_VALUE) and not (noMix and float(entry[mixedLabel]) > 0.5):
            featureMatrix.append([float(entry[k]) for k in sortedKeys])
            labelMatrix.append(featureLabel)
        counter += 1
        try:
            entry = next(reader)
        except (StopIteration, IOError):
            entry = None

    infile.close()
    return np.array(featureMatrix, dtype=np.float64), np.array(labelMatrix, dtype=str), np.array(sortedKeys)


# Creates a dictionary of SciKit scorer objects. Each object considers features from a specific class out of those
# given as input, and the metric used here is the F-Score
def getScorerObjects(labels):
    labelSet = set(labels)
    scorers = {}
    for label in labelSet:
        scorers[label] = make_scorer(f1_score, average=None, labels=[label])
    scorers['weighted'] = make_scorer(f1_score, average='weighted')
    return scorers


# This script takes as input a CSV file containing features suitable for machine learning classification. It will test
# the file over a set of classifiers and report the obtained accuracy
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Fin-J Fault Detection Test Tool")
    parser.add_argument("-f", action="store", dest="source", type=str, default=None,
                        help="Path to the CSV features file to be used.")
    parser.add_argument("-m", action="store", dest="maxf", type=int, default=-1,
                        help="Maximum number of features to be processed")
    parser.add_argument("-p", action="store", dest="impMetrics", type=int, default=0,
                        help="Number of most important metrics to print when using a Random Forest Classifier.")
    parser.add_argument("-n", action="store_true", dest="noMix",
                        help="Use only features corresponding to non-ambiguous states.")
    parser.add_argument("-d", action="store_true", dest="discardDerivs",
                        help="Discard metrics related to first-order derivatives in features.")
    args = parser.parse_args()
    if args.source is None:
        print("You must supply the path to the features file that must be used!")
        exit(-1)
    if args.maxf < -1 or args.maxf == 0:
        args.maxf = -1
    print('---------- FINJ CROSS-VALIDATION TOOL ----------')
    print('- Input filename: %s' % args.source)
    if args.noMix:
        print('- Ambiguous features are being discarded.')
    if args.discardDerivs:
        print('- First-order derivatives are being discarded from features.')
    print('- Loading features...')
    features, labels, metricKeys = loadFeatures(args.source, maxFeatures=args.maxf, noMix=args.noMix, discardDerivs=args.discardDerivs)
    print('- Feature length is %s...' % len(features[0, :]))
    print('- Number of features is %s...' % len(features[:, 0]))
    print('- Performing cross-validation...')
    print('---------------')
    warnings.filterwarnings('ignore')
    # After loading the features, we perform cross-validation over the list of classifiers defined above, and print
    # the results.
    for clf in clfList:
        scorers = getScorerObjects(labels)
        scores = cross_validate(clf, features, labels, cv=5, scoring=scorers, n_jobs=-1)
        print('- Classifier: %s' % clf.__class__.__name__)
        mean = scores['test_weighted'].mean()
        confidence = scores['test_weighted'].std() * 1.96 / np.sqrt(len(scores['test_weighted']))
        print('- Global F-Score : %s (+/- %s)' % (mean, confidence))
        for k, v in scores.items():
            if 'test_' in k and k != 'test_weighted':
                mean = scores[k].mean()
                confidence = scores[k].std() * 1.96 / np.sqrt(len(scores[k]))
                print('---- %s F-Score : %s (+/- %s)' % (k.split('_')[1], mean, confidence))
        if clf.__class__.__name__ == 'RandomForestClassifier' and args.impMetrics > 0:
            # We fit the random forest classifier just to extract the information regarding
            # which are the most important metrics in the features
            clf.fit(features, labels)
            importances = clf.feature_importances_
            indices = np.argsort(importances)[::-1]
            print('- Most important features:')
            for idx in range(args.impMetrics if args.impMetrics < len(indices) else len(indices)):
                metric = indices[idx]
                print('---- %s: %s' % (metricKeys[metric], importances[metric]))
        print('---------------')
    exit(0)
