from fault_injector.injection.fault_injector_client import InjectorClient
from fault_injector.io.reader import CSVReader
import logging, sys

logging.basicConfig(stream=sys.stdout, level=logging.INFO)


reader = CSVReader('workloads/sample_workload.csv')
inj = InjectorClient.build('config/client.config')
inj.inject(reader)
inj.stop()
