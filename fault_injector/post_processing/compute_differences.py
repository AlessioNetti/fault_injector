from csv import DictWriter, DictReader
from os.path import split
import argparse


def convertToDifferences(inpath, outpath):
    fieldBlacklist = ['#Time', 'Time_usec', 'ProducerName', 'component_id', 'job_id']
    infile = open(inpath, 'r')
    reader = DictReader(infile)

    try:
        metricSet = next(reader)
    except (StopIteration, IOError):
        infile.close()
        return

    outfile = open(outpath, 'w')
    writer = DictWriter(outfile, fieldnames=reader.fieldnames)
    fieldict = {k: k for k in reader.fieldnames}
    writer.writerow(fieldict)

    try:
        entry = next(reader)
    except (StopIteration, IOError):
        infile.close()
        return

    while entry is not None:
        diff = {}
        for k in entry.keys():
            if k not in fieldBlacklist:
                diff[k] = int(entry[k]) - int(metricSet[k])
                assert diff[k] >= 0, 'The input file is not incremental!'
            else:
                diff[k] = entry[k]
        writer.writerow(diff)
        metricSet = entry
        try:
            entry = next(reader)
        except (StopIteration, IOError):
            infile.close()
            entry = None
    infile.close()
    outfile.close()


# This script takes as input a CSV system performance metrics file, and computes its first-order derivatives equivalent
# by performing differences between consecutive entries
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Fin-J First-Order Derivatives Converter Tool")
    parser.add_argument("-f", action="store", dest="source", type=str, default=None, help="Path to the CSV log file to be converted.")
    args = parser.parse_args()
    if args.source is None:
        print("You must supply the path to the log file that must be converted!")
        exit(-1)
    in_path = args.source
    out_path = split(in_path)[0] + 'diff_' + split(in_path)[1]
    convertToDifferences(in_path, out_path)
    exit(0)
