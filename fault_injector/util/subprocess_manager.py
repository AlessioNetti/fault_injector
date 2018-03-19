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
