from fault_injector.io.reader import ExecutionLogReader
from fault_injector.io.writer import CSVWriter
from fault_injector.util.misc import format_task_filename, format_task_filename_cores
from fault_injector.post_processing.constants import timeLabel, benchmarkLabel, faultLabel
from csv import DictWriter
from os.path import split
import argparse



def fillTimestamps(writer, curr_bench, curr_fault, start, end, step):
    """
    Given a benchmark and fault label, and a start/end timestamp couple, this function writes all timestamps with the
    specified label from the start to the end of the interval

    :param writer: Writer object for the output CSV file
    :param curr_bench: Label(s) for the currently running benchmark
    :param curr_fault: Label(s) for the currently running fault programs
    :param start: Starting timestamp for the current system status
    :param end: End timestamp (exclusive) for the current system state
    :param step: Step between each filled timestamp in the interval
    """
    label_separator = CSVWriter.L1_DELIMITER_CHAR
    curr_timestamp = start
    buffdict = {}
    while curr_timestamp < end:
        buffdict[timeLabel] = curr_timestamp
        if len(curr_fault) > 0:
            buffdict[faultLabel] = label_separator.join(curr_fault)
        if len(curr_bench) > 0:
            buffdict[benchmarkLabel] = label_separator.join(curr_bench)
        writer.writerow(buffdict)
        curr_timestamp += step


def convertLogToLabelFile(inpath, outpath, step=1, showNums=False):
    """
    Reads a FINJ execution record, and outputs a file containing timestamps mapped to task labels

    :param inpath: Path of the input FINJ execution record
    :param outpath: Output path for the processed file
    :param step: Step to use between timestamps in the output file
    :param showNums: By default, each task label also contains the list of cores assigned to the task. If this argument
        is True, the sequence number of the task is used instead
    :return:
    """
    labelNames = [timeLabel, faultLabel, benchmarkLabel]
    reader = ExecutionLogReader(inpath)
    outfile = open(outpath, 'w')
    writer = DictWriter(outfile, fieldnames=labelNames, delimiter=CSVWriter.DELIMITER_CHAR, quotechar=CSVWriter.QUOTE_CHAR,
                        restval=CSVWriter.NONE_VALUE, extrasaction='ignore')
    fieldict = {k: k for k in labelNames}
    writer.writerow(fieldict)
    entry = reader.read_entry()
    # Structures to keep track of currently running tasks
    curr_bench = []
    curr_fault = []
    curr_timestamp = 0
    while entry is not None:
        # We process each entry in the execution record and keep track of which tasks are running at each timestamp
        # Every time the system's status changes (tasks end or start) we write all timestamps with their labels in
        # order up to the current time, starting from the previous state
        if entry['type'] == 'command_session_e':
            fillTimestamps(writer, curr_bench, curr_fault, curr_timestamp, int(entry['timestamp']), step)
            break
        elif entry['type'] == 'status_start':
            fillTimestamps(writer, curr_bench, curr_fault, curr_timestamp, int(entry['timestamp']), step)
            taskname = format_task_filename(entry) if showNums else format_task_filename_cores(entry)
            if entry['isFault'] != 'True':
                curr_bench.append(taskname)
            else:
                curr_fault.append(taskname)
        elif entry['type'] == 'status_end' or entry['type'] == 'status_err':
            fillTimestamps(writer, curr_bench, curr_fault, curr_timestamp, int(entry['timestamp']), step)
            taskname = format_task_filename(entry) if showNums else format_task_filename_cores(entry)
            if entry['isFault'] != 'True':
                curr_bench.remove(taskname)
            else:
                curr_fault.remove(taskname)
        elif entry['type'] == 'status_reset':
            fillTimestamps(writer, curr_bench, curr_fault, curr_timestamp, int(entry['timestamp']), step)
            curr_bench = []
            curr_fault = []
        if entry['type'] != 'status_restart':
            curr_timestamp = int(entry['timestamp'])
        entry = reader.read_entry()
    reader.close()
    outfile.close()


# This script takes as input a FIN-J execution log file, and converts it to a label file, in which timestamps are
# mapped to the task(s) that was running at that specific time
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Fin-J Log to Label Converter Tool")
    parser.add_argument("-f", action="store", dest="source", type=str, default=None, help="Path to the CSV log file to be converted.")
    parser.add_argument("-n", action="store_true", dest="showNums", help="Show sequence numbers instead of assigned cores.")
    parser.add_argument("-s", action="store", dest="step", type=int, default=1, help="Step to increment the timestamps.")
    args = parser.parse_args()
    if args.source is None:
        print("You must supply the path to the log file that must be converted!")
        exit(-1)
    if args.step < 1:
        args.step = 1
    in_path = args.source
    out_path = split(in_path)[0] + 'labels_' + split(in_path)[1]
    convertLogToLabelFile(in_path, out_path, args.step, args.showNums)
    exit(0)
