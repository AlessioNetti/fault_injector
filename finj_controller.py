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

from fault_injector.injection.fault_injector_controller import InjectorController
from fault_injector.io.reader import CSVReader
import logging, sys, argparse


# Configuring the input arguments to the script, and parsing them
parser = argparse.ArgumentParser(description="Fin-J Fault Injection Controller")
parser.add_argument("-c", action="store", dest="config", type=str, default=None, help="Path to a configuration file.")
parser.add_argument("-w", action="store", dest="workload", type=str, default=None, help="Path of the CSV workload file.")
parser.add_argument("-m", action="store", dest="max_tasks", type=int, default=None, help="Maximum number of tasks to be injected.")
parser.add_argument("-a", action="store", dest="hosts", type=str, default=None, help="Addresses of hosts in <ip>:<port> format, separated by commas.")
parser.add_argument("-p", action="store_true", dest="probe", help="Enable Probe mode, suppressing all output except errors.")

args = parser.parse_args()

if args.probe:
    logging.basicConfig(stream=sys.stdout, level=logging.WARNING)
else:
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)

hosts = [addr.strip() for addr in args.hosts.split(',')] if args.hosts is not None else None

reader = CSVReader(path=args.workload) if args.workload is not None else None
inj = InjectorController.build(config=args.config, hosts=hosts)
inj.inject(reader=reader, max_tasks=args.max_tasks, suppress_output=args.probe)
inj.stop()
