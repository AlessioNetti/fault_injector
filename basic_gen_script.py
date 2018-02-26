from fault_injector.workload_generator.workload_generator import WorkloadGenerator
from scipy.stats import norm, weibull_min

faults = ['faultlib/leak {0}',
          'faultlib/leak {0} l',
          'faultlib/memeater {0}',
          'faultlib/memeater {0} l',
          'faultlib/dial {0}',
          'faultlib/dial {0} l']

out = '../workloads/gen_workload.csv'
size = 1000
span = 3600 * 48

if __name__ == '__main__':
    generator = WorkloadGenerator(path=out, limit_size=size, limit_span=span)

    generator.durationGenerator.value_range = (10, 120)
    generator.durationGenerator.set_distribution(norm, 60, 5)
    generator.durationGenerator.show_fit()

    generator.timeGenerator.value_range = (300, 600)
    generator.timeGenerator.set_distribution(weibull_min, 1, 400, 10)
    generator.timeGenerator.show_fit()

    exit()
