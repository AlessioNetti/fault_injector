from fault_injector.io.reader import ExecutionLogReader
from fault_injector.io.writer import CSVWriter
from fault_injector.util.misc import format_task_filename, format_task_filename_cores
from csv import DictWriter
from os.path import split
import argparse


def fillTimestamps(writer, curr_bench, curr_fault, start, end, step):
    label_separator = CSVWriter.L1_DELIMITER_CHAR
    curr_timestamp = start
    buffdict = {}
    while curr_timestamp < end:
        buffdict['#Time'] = curr_timestamp
        if len(curr_fault) > 0:
            buffdict['#Fault'] = label_separator.join(curr_fault)
        if len(curr_bench) > 0:
            buffdict['#Benchmark'] = label_separator.join(curr_bench)
        writer.writerow(buffdict)
        curr_timestamp += step


def convertLogToLabelFile(inpath, outpath, step=1, showCores=False):
    labelNames = ['#Time', '#Fault', '#Benchmark']
    reader = ExecutionLogReader(inpath)
    outfile = open(outpath, 'w')
    writer = DictWriter(outfile, fieldnames=labelNames, delimiter=CSVWriter.DELIMITER_CHAR, quotechar=CSVWriter.QUOTE_CHAR,
                        restval=CSVWriter.NONE_VALUE, extrasaction='ignore')
    fieldict = {k: k for k in labelNames}
    writer.writerow(fieldict)
    entry = reader.read_entry()
    curr_bench = []
    curr_fault = []
    curr_timestamp = 0
    while entry is not None:
        if entry['type'] == 'command_session_e':
            fillTimestamps(writer, curr_bench, curr_fault, curr_timestamp, int(entry['timestamp']), step)
            break
        elif entry['type'] == 'status_start':
            fillTimestamps(writer, curr_bench, curr_fault, curr_timestamp, int(entry['timestamp']), step)
            taskname = format_task_filename(entry) if not showCores else format_task_filename_cores(entry)
            if entry['isFault'] != 'True':
                curr_bench.append(taskname)
            else:
                curr_fault.append(taskname)
        elif entry['type'] == 'status_end' or entry['type'] == 'status_err':
            fillTimestamps(writer, curr_bench, curr_fault, curr_timestamp, int(entry['timestamp']), step)
            taskname = format_task_filename(entry) if not showCores else format_task_filename_cores(entry)
            if entry['isFault'] != 'True':
                curr_bench.remove(taskname)
            else:
                curr_fault.remove(taskname)
        elif entry['type'] == 'status_reset':
            fillTimestamps(writer, curr_bench, curr_fault, curr_timestamp, int(entry['timestamp']), step)
            curr_bench = []
            curr_fault = []
        curr_timestamp = int(entry['timestamp'])
        entry = reader.read_entry()
    reader.close()
    outfile.close()


# This script takes as input a FIN-J execution log file, and converts it to a label file, in which timestamps are
# mapped to the task(s) that was running at that specific time
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Fin-J Log to Label Converter Tool")
    parser.add_argument("-f", action="store", dest="source", type=str, default=None, help="Path to the CSV log file to be converted.")
    parser.add_argument("-c", action="store_true", dest="showCores", help="Show assigned cores to tasks instead of sequence numbers.")
    parser.add_argument("-s", action="store", dest="step", type=int, default=1, help="Step to increment the timestamps.")
    args = parser.parse_args()
    if args.source is None:
        print("You must supply the path to the log file that must be converted!")
        exit(-1)
    if args.step < 1:
        args.step = 1
    in_path = args.source
    out_path = split(in_path)[0] + 'labels_' + split(in_path)[1]
    convertLogToLabelFile(in_path, out_path, args.step, args.showCores)
    exit(0)
