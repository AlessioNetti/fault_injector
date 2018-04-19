import json, logging
from copy import copy


class ConfigLoader:

    logger = logging.getLogger('ConfigLoader')

    _dfl_config = {
        "RESULTS_DIR": 'results',
        "SKIP_EXPIRED": True,
        "RETRY_TASKS": True,
        "RETRY_TASKS_ON_ERROR": False,
        "ABRUPT_TASK_KILL": True,
        "RECOVER_AFTER_DISCONNECT": False,
        "LOG_OUTPUTS": True,
        "ENABLE_ROOT": False,
        "SERVER_PORT": 30000,
        "MAX_REQUESTS": 20,
        "RETRY_INTERVAL": 600,
        "RETRY_PERIOD": 30,
        "PRE_SEND_INTERVAL": 600,
        "WORKLOAD_PADDING": 20,
        "NUMA_CORES_FAULTS": None,
        "NUMA_CORES_BENCHMARKS": None,
        "HOSTS": [],
        "AUX_COMMANDS": []
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
