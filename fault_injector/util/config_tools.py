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

import json, logging
from copy import copy


class ConfigLoader:
    """
    Class that provides static methods to load configuration descriptions (in form of dictionaries) from JSON files
    """

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
        "SESSION_WAIT": 60,
        "NUMA_CORES_FAULTS": None,
        "NUMA_CORES_BENCHMARKS": None,
        "HOSTS": [],
        "AUX_COMMANDS": []
    }

    @staticmethod
    def getConfig(file=None):
        """
        Loads a configuration dictionary from an input file, or return the default configuration

        :param file: Path to a JSON file containing configuration entries for FINJ. If None is supplied, the default
            configuration is used
        :return: A configuration dictionary for FINJ
        """
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
