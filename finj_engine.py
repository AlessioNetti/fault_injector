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

from fault_injector.injection.fault_injector_engine import InjectorEngine
import logging, sys, argparse


# Configuring the input arguments to the script, and parsing them
parser = argparse.ArgumentParser(description="Fin-J Fault Injection Engine")
parser.add_argument("-c", action="store", dest="config", type=str, default=None, help="Path to a configuration file.")
parser.add_argument("-p", action="store", dest="port", type=int, default=None, help="Listening port for the server.")

args = parser.parse_args()

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

inj = InjectorEngine.build(config=args.config, port=args.port)
inj.listen()
