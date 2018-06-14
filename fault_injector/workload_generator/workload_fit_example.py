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

from fault_injector.workload_generator.workload_generator import WorkloadGenerator
from scipy.stats import norm, exponweib
import datetime, calendar

# The list of fault commands to be injected.
# It is suggested to always use FULL paths, to avoid relative path issues
faults = ['faultlib/leak {0}',
          'faultlib/leak {0} l',
          'faultlib/memeater {0}',
          'faultlib/memeater {0} l',
          'faultlib/dial {0}',
          'faultlib/dial {0} l']

# The list of benchmarks to be used
benchmarks = ['faultlib/linpack',
              'faultlib/stream',
              'faultlib/generic']

# Input file on which fitting must be performed
in_path = 'workloads/pnnl_event_trace.csv'
# Output path of the generated workload
out = 'workloads/gen_workload.csv'
# Maximum time span (in seconds) of the workload
span = 3600 * 48


# Parsing the input data, which has a custom CSV format
def parse_data(path):
    in_file = open(path, 'r', errors='ignore')
    data = []
    for line in in_file:
        entry = line.split(',')
        if len(entry) > 0 and '/' in entry[0] and ':' in entry[0]:
            entry = entry[0].strip()
            # Converting the datetimes of the entries in UTC timestamps
            date_obj = datetime.datetime.strptime(entry, "%m/%d/%Y %H:%M")
            data.append(calendar.timegm(date_obj.utctimetuple()))
    in_file.close()
    data.sort()
    data_filtered = []
    # Calculating the difference between consecutive entries, i.e. fault inter-arrival times
    for i in range(1, len(data)):
        point = data[i] - data[i - 1]
        # This serves to remove cascading faults, which would skew the distribution too much
        if point > 300:
            data_filtered.append(point)
    return data_filtered


if __name__ == '__main__':
    # Acquiring fault inter-arrival time data from a real fault trace
    data = parse_data(in_path)
    generator = WorkloadGenerator(path=out)
    # We set the fault generator so that a Normal distribution is used for the durations, and a Weibull distribution is
    # used for the inter-fault times
    generator.faultDurGenerator.set_distribution(norm(loc=60, scale=6))
    # Fitting a distribution over the acquired data
    generator.faultTimeGenerator.fit_data(exponweib, data, loc=700, scale=650)
    generator.faultTimeGenerator.show_fit(val_range=(200, 900), n_bins=20)
    # We let the workload generator set the benchmark generator automatically, by imposing that roughly 80%
    # of the workload time must be spent in "busy" operation
    generator.autoset_bench_generators(busy_time=0.8, num_tasks=20, span_limit=span)
    # We start the workload generation process
    generator.generate(faults, benchmarks, span_limit=span)

    exit()
