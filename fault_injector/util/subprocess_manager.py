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

import subprocess, os, logging
from shlex import split


class SubprocessManager:
    """
    Simple class that allows to spawn (and then terminate) a series of subprocesses tied to tasks that need to run
    alongside a main process
    """

    # Logger for the class
    logger = logging.getLogger('SubprocessManager')

    def __init__(self, commands=None):
        """
        Constructor for the class

        :param commands: The list of command strings for each task that must be launched
        """
        self._commands = commands
        self._processes = None

    def start_subprocesses(self):
        """
        Spawns subprocesses related to all commands given as input to the class
        """
        if self._commands is None or len(self._commands) == 0 or self._processes is not None:
            return None
        procs = []
        self._processes = []
        for c in self._commands:
            args = split(c, posix=os.name == 'posix')
            try:
                p = subprocess.Popen(args=args)
                procs.append(p)
                self._processes.append(p)
            except(OSError, FileNotFoundError):
                pass
        return procs

    def stop_subprocesses(self):
        """
        Stops all previously spawned processes by a call to start_subprocesses
        """
        if self._processes is not None and len(self._processes) > 0:
            for p in self._processes:
                try:
                    p.terminate()
                    p.wait()
                except PermissionError:
                    SubprocessManager.logger.error("Permission denied to stop PID %s. Try running the daemon as root" % p.pid)
        self._processes = None
