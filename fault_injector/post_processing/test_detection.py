from csv import DictReader
from fault_injector.io.writer import CSVWriter
from fault_injector.post_processing.constants import faultLabel, benchmarkLabel, timeLabel, mixedLabel, busyFaults
from sklearn.model_selection import cross_validate
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import make_scorer, f1_score
import numpy as np
import argparse


# List of classifiers to be used for detection
clfList = [RandomForestClassifier(n_estimators=21)]


# Given the filepath of an input CSV feature file, this function reads all features from the file and stores them in
# a Numpy matrix suitable for use with SciKit classifiers. It returns the feature matrix and the list of labels for
# each feature.
def loadFeatures(inpath, maxFeatures=-1, noMix=False):
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
    print('- Loading features...')
    while entry is not None and (maxFeatures == -1 or counter < maxFeatures):
        if sortedKeys is None:
            sortedKeys = sorted([k for k in entry.keys() if k not in fieldBlacklist])
        featureLabel = entry[faultLabel].split('_')[0]
        if (featureLabel not in busyFaults or entry[benchmarkLabel] != CSVWriter.NONE_VALUE) and not (noMix and float(entry[mixedLabel]) > 0.5):
            featureMatrix.append([float(entry[k]) for k in sortedKeys])
            labelMatrix.append(featureLabel)
        counter += 1
        try:
            entry = next(reader)
        except (StopIteration, IOError):
            infile.close()
            entry = None

    infile.close()
    return np.array(featureMatrix, dtype=np.float64), np.array(labelMatrix, dtype=str)


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
    parser.add_argument("-n", action="store_true", dest="noMix",
                        help="Use only features corresponding to non-ambiguous states.")
    args = parser.parse_args()
    if args.source is None:
        print("You must supply the path to the features file that must be used!")
        exit(-1)
    if args.maxf < -1:
        args.maxf = -1
    in_path = args.source
    features, labels = loadFeatures(in_path, maxFeatures=args.maxf, noMix=args.noMix)
    scorers = getScorerObjects(labels)
    print('- Performing cross-validation...')
    print('---------------')
    # After loading the features, we perform cross-validation over the list of classifiers defined above, and print
    # the results.
    for clf in clfList:
        scores = cross_validate(clf, features, labels, cv=5, scoring=scorers)
        print('- Classifier: %s' % clf.__class__.__name__)
        print('- Global F-Score : %s (+/- %s)' % (scores['test_weighted'].mean(), scores['test_weighted'].std() * 2))
        for k, v in scores.items():
            if 'test_' in k and k != 'test_weighted':
                print('---- %s F-Score : %s (+/- %s)' % (k.split('_')[1], scores[k].mean(), scores[k].std() * 2))
        print('---------------')
    exit(0)
