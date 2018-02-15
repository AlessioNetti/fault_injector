from fault_injector.injection.fault_injector_server import InjectorServer
import logging, sys, argparse

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

# Configuring the input arguments to the script, and parsing them
parser = argparse.ArgumentParser(description="Fin-J Fault Injection Server")
parser.add_argument("-c", action="store", dest="config", type=str, default=None, help="Path to a configuration file.")
parser.add_argument("-p", action="store", dest="port", type=int, default=None, help="Listening port for the server.")

args = parser.parse_args()

inj = InjectorServer.build(config='config/server.config', port=args.port)
inj.listen()
