from fault_injector.injection.fault_injector_server import InjectorServer
import logging, sys

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

inj = InjectorServer.build('config/server.config')
inj.listen()
