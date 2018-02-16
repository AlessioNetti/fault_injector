from fault_injector.injection.fault_injector_client import InjectorClient
from fault_injector.io.reader import CSVReader
import logging, sys, argparse

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

# Configuring the input arguments to the script, and parsing them
parser = argparse.ArgumentParser(description="Fin-J Fault Injection Client")
parser.add_argument("-c", action="store", dest="config", type=str, default=None, help="Path to a configuration file.")
parser.add_argument("-w", action="store", dest="workload", type=str, default=None, help="Path of the CSV workload file.")
parser.add_argument("-m", action="store", dest="max_tasks", type=int, default=None, help="Maximum number of tasks to be injected.")
parser.add_argument("-a", action="store", dest="hosts", type=str, default=None, help="Addresses of hosts in <ip>:<port> format, separated by commas.")

args = parser.parse_args()

hosts = [addr.strip() for addr in args.hosts.split(',')] if args.hosts is not None else None

reader = CSVReader(path=args.workload) if args.workload is not None else None
inj = InjectorClient.build(config=args.config, hosts=hosts)
inj.inject(reader=reader, max_tasks=args.max_tasks)
inj.stop()
