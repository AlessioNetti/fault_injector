from fault_injector.workload_generator.workload_generator import WorkloadGenerator
from scipy.stats import norm, exponweib

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

# Output path of the generated workload
out = 'workloads/gen_workload.csv'
# Maximum time span (in seconds) of the workload
span = 3600 * 48

if __name__ == '__main__':
    generator = WorkloadGenerator(path=out)
# We set the fault generator so that a Normal distribution is used for the durations, and a Weibull distribution is
# used for the inter-fault times
    generator.faultDurGenerator.set_distribution(norm(loc=60, scale=6))
    generator.faultTimeGenerator.set_distribution(exponweib(a=10, c=1, loc=300, scale=15))
# We let the workload generator set the benchmark generator automatically, by imposing that roughly 80% of the workload
# time must be spent in "busy" operation
    generator.autoset_bench_generators(busy_time=0.8, num_tasks=20, span_limit=span)
# We start the workload generation process
    generator.generate(faults, benchmarks, span_limit=span)

    exit()
