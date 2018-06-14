"""
MIT License

Copyright (c) 2018 AlessioNetti

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from csv import DictWriter, DictReader
from os.path import split
import argparse


def convertToDifferences(inpath, outpath):
    """
    This function considers a CSV input file, and writes an output file containing the first-order derivatives for each
    metric

    :param inpath: The path to the input CSV file to be converted
    :param outpath: The path to the output file that will contain first-order derivatives
    """
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
# by performing subtractions between consecutive entries
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
