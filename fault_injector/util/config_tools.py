import json, logging
from copy import copy


class ConfigLoader:

    logger = logging.getLogger(__name__)

    _dfl_config = {
        "RESULTS_DIR": "results",
        "MAX_REQUESTS": 20,
        "SKIP_EXPIRED": True,
        "RETRY_TASKS": True,
        "ABRUPT_TASK_KILL": True,
        "MAX_CONNECTIONS": 100,
        "SOCKET_TIMEOUT": 10,
        "RETRY_INTERVAL": 600,
        "RETRY_PERIOD": 30,
        "PRE_SEND_INTERVAL": 600,
        "WORKLOAD_PADDING": 20,
        "HOSTS": []
    }

    @staticmethod
    def getConfig(file=None):
        if file is None:
            return copy(ConfigLoader._dfl_config)
        else:
            cfg = copy(ConfigLoader._dfl_config)
            try:
                cfg_file = json.load(open(file))
                cfg.update(cfg_file)
            except (FileNotFoundError, IOError, ValueError):
                ConfigLoader.logger.error("Configuration file %s cannot be read" % file)
                pass
            return cfg
