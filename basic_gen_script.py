from fault_injector.workload_generator.workload_generator import WorkloadGenerator
from scipy.stats import norm, exponweib

faults = ['faultlib/leak {0}',
          'faultlib/leak {0} l',
          'faultlib/memeater {0}',
          'faultlib/memeater {0} l',
          'faultlib/dial {0}',
          'faultlib/dial {0} l']

out = 'workloads/gen_workload.csv'
size = 1000
span = 3600 * 48

if __name__ == '__main__':
    generator = WorkloadGenerator(path=out, limit_size=size, limit_span=span)

    generator.durationGenerator.set_distribution(norm(loc=60, scale=5))
    #generator.durationGenerator.show_fit((10, 120))

    generator.timeGenerator.set_distribution(exponweib(a=10, c=1, loc=0, scale=1))
    #generator.timeGenerator.show_fit((-10, 10))

    generator.generate(faults, None)

    exit()
