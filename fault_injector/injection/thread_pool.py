import logging, subprocess, os
from abc import ABC, abstractmethod
from time import time
from threading import Thread, Lock, Semaphore, Condition, current_thread
from subprocess import TimeoutExpired
from fault_injector.network.msg_entity import MessageEntity
from fault_injector.network.msg_builder import MessageBuilder
from fault_injector.io.task import Task
from shlex import split


class ThreadWrapper(Thread):
    """
    Wrapper class for Thread
    
    This class provides some facilities for the management of subprocesses spawned by threads: it allows for safe
    monitoring and termination by the main process, handling mutual exclusion issues as well
    """

    def __init__(self, **kwargs):
        """
        Constructor for the class
        
        :param kwargs: All of the arguments supported by Thread
        """
        super().__init__(**kwargs)
        # Popen object for the underlying subprocess
        self._process = None
        # Boolean flag that dictates whether the thread has to terminate or not
        self._hasToFinish = False
        # Lock object for access to both the Popen object and hasToFinish field
        self._lock = Lock()

    def terminate(self):
        """
        Flags the thread for termination
        """
        self._lock.acquire()
        self._hasToFinish = True
        self._lock.release()

    def has_to_terminate(self):
        """
        Returns the current termination status of the thread
        
        :return: True if the thread has to terminate, False otherwise 
        """
        self._lock.acquire()
        t = self._hasToFinish
        self._lock.release()
        return t

    def is_active(self):
        """
        Returns True the current status of the thread

        :return: True if the thread is currently running a subprocess, False otherwise
        """
        st = False
        self._lock.acquire()
        if self._process is not None and self._process.returncode is None:
            st = True
        self._lock.release()
        return st

    def start_process(self, **kwargs):
        """
        Starts a subprocess, if the thread has not been flagged for termination
        
        :param kwargs: All of the arguments supported by Popen
        :return: a Popen object if successful, None otherwise
        """
        self._lock.acquire()
        p = None
        if not self._hasToFinish:
            try:
                p = subprocess.Popen(**kwargs)
                self._process = p
            except(OSError, FileNotFoundError):
                self._process = None
                p = None
        self._lock.release()
        return p

    def force_stop_process(self):
        """
        Kills the underlying subprocess, if running
        """
        self._lock.acquire()
        if self._process is not None:
            self._process.poll()
            if self._process.returncode is None:
                self._process.kill()
                self._process.wait()
        self._lock.release()


class ThreadPool(ABC):
    """
    Abstract class for a generic thread pool.
    
    The class is based on the producer-consumer paradigm: the threads interact with a queue, which contains 
    user-submitted tasks. When new tasks are available, some worker threads are woken up, and they execute such
    task.
    """

    # Logger for the class
    logger = logging.getLogger(__name__)

    def __init__(self, max_requests=20):
        """
        Constructor for the class
        
        :param max_requests: Number of maximum concurrent requests (threads). If more requests are submitted
            concurrently, they will wait in the queue
        """
        # Semaphore and lock to regulate access to the queue
        self._queueSem = Semaphore(0)
        self._queueLock = Lock()
        self._queue = []
        # Boolean flag for thread management
        self._initialized = False
        self._terminating = False
        self._maxRequests = max_requests if max_requests > 0 else 20
        # The list of worker thread objects
        self._threads = []

    def active_tasks(self):
        """
        Returns the number of threads in the pool that are currently running subprocesses

        :return: The number of currently active threads
        """
        return sum(t.is_active() for t in self._threads)

    def start(self):
        """
        Method that starts up the thread pool, spawning new threads that go into sleep until tasks are submitted
        """
        if not self._initialized:
            # The list of worker thread objects
            self._threads = []
            for i in range(self._maxRequests):
                self._threads.append(ThreadWrapper(target=self._working_loop))
            for t in self._threads:
                t.start()
            self._initialized = True
            self._terminating = False
            ThreadPool.logger.debug('Thread pool successfully started')

    def stop(self):
        """
        Method that terminates the thread pool, joining all currently running threads
        """
        if self._initialized:
            self._terminating = True
            # First of all, we flag all threads for termination
            for i in range(len(self._threads)):
                self._threads[i].terminate()
            # We perform as many 'releases' on the semaphore as the threads, in order to force them to awaken
            for i in range(len(self._threads)):
                self._queueSem.release()
            # Next, we join all the threads, that should have terminated by now
            for i in range(len(self._threads)):
                self._threads[i].join()
                self._threads[i] = None
            self._threads.clear()
            self._initialized = False
            ThreadPool.logger.debug('Thread pool successfully stopped')

    def submit_task(self, task):
        """
        Allows to submit a new task to be performed, into the queue
        
        :param task: The task object (implementation-dependent)
        """
        if self._terminating or not self._initialized:
            ThreadPool.logger.error('Cannot submit tasks to either terminated or uninitialized pools')
            return
        # Before submitting the task, we check if all threads are alive
        self._check_threads()
        self._queueLock.acquire()
        self._queue.append(task)
        self._queueLock.release()
        self._queueSem.release()

    def get_pending_tasks(self):
        """
        Returns the number of currently pending tasks in the queue
        
        :return: the number of pending tasks
        """
        self._queueLock.acquire()
        qlen = len(self._queue)
        self._queueLock.release()
        return qlen

    def _check_threads(self):
        """
        Internal method that checks for the liveness of all working threads
        
        If some threads are dead, the method will automatically respawn them
        """
        if self._terminating or not self._initialized:
            return
        for i in range(len(self._threads)):
            if not self._threads[i].isAlive():
                ThreadPool.logger.warning('A thread in the pool died unexpectedly, will be restored')
                self._threads[i].join()
                self._threads[i] = ThreadWrapper(target=self._working_loop)
                self._threads[i].start()

    def _working_loop(self):
        """
        Implements the basic loop of a working thread
        
        A thread starts by being in idle state and waiting for a new task in the queue to become available. When this
        happens, the thread is woken up, it executes the task, and goes back to sleep.
        """
        while True:
            self._queueSem.acquire()
            if current_thread().has_to_terminate():
                break
            self._queueLock.acquire()
            task = None
            if len(self._queue) > 0:
                task = self._queue.pop(0)
            self._queueLock.release()
            if task is not None:
                self._execute_task(task)

    @abstractmethod
    def _execute_task(self, task):
        """
        This method contains the specific execution logic for the selected task type, and must be implemented
        
        :param task: the task object (implementation-dependent)
        """
        raise NotImplementedError('This method must be implemented!')


class InjectionThreadPool(ThreadPool):
    """
    Implementation of ThreadPool, focused on the execution of fault injection and benchmark tasks
    """

    # Logger for the class
    logger = logging.getLogger(__name__)

    CORRECTION_THRESHOLD = 60

    def __init__(self, msg_server, max_requests=20, skip_expired=True, retry_tasks=True):
        """
        Constructor for the class
        
        :param msg_server: The MessageEntity object to be used for broadcast communication
        :param max_requests: The maximum number of concurrent requests (like in ThreadPool)
        :param skip_expired: Boolean flag. If True, tasks whose start timestamp has expired will not be executed
        :param retry_tasks: Boolean flag. If True, tasks terminating earlier than their expected duration will be
            re-executed
        """
        super().__init__(max_requests)
        assert isinstance(msg_server, MessageEntity), 'Messaging object must be a MessageEntity instance!'
        self._server = msg_server
        self._skip_expired = skip_expired
        self._retry_tasks = retry_tasks
        # This flag determines whether we are running in a posix system or not. Used for shell argument parsing
        self._posix_shell = os.name == 'posix'
        # Timestamps for the starting time of the injection session in absolute and relative time
        self._session_start = 0
        self._session_start_abs = 0
        self._correction_factor = 0
        # Condition object used to wake up threads that are in sleep state (waiting for their tasks' starting times)
        self._sleepCondition = Condition()

    def reset_session(self, timestamp, abs_timestamp):
        """
        Resets the internal timestamps to the starting time of a new injection session
        
        :param timestamp: The relative timestamp of the new injection session
        :param abs_timestamp: The absolute timestamp of the new injection session
        """
        self._session_start = timestamp
        self._session_start_abs = abs_timestamp

    def correct_time(self, timestamp):
        """
        This method applies correction to the local clock if necessary

        We compare the timestamp of the injector server (in relative workload time) to the local timestamp of the pool.
        If the local clock drifts against the remote clock by more than a threshold, we compute an adaptive correction
        factor for it. In other words, the correction is applied when the pool is "too much behind or in advance in
        the workload's time" against the remote clock.

        :param timestamp: The workload timestamp of the injector host
        """
        my_timestamp = time() - self._session_start_abs + self._session_start
        diff = timestamp - my_timestamp - self._correction_factor
        if abs(diff) > InjectionThreadPool.CORRECTION_THRESHOLD:
            InjectionThreadPool.logger.warning("Clock is drifting by %s secs against the injector's clock" % str(diff))
            self._correction_factor += 0.1 * diff

    def stop(self, kill_abruptly=True):
        """
        Method that terminates the thread pool, joining all currently running threads
        
        :param kill_abruptly: Boolean flag. If True running tasks, at the moment termination of the pool is requested,
            will be killed abruptly with process.kill(), without waiting for their termination
        """
        if self._initialized:
            # First of all, we flag all threads for termination
            for i in range(len(self._threads)):
                self._threads[i].terminate()
            # We perform as many 'releases' on the semaphore as the threads, in order to force them to awaken
            for i in range(len(self._threads)):
                self._queueSem.release()
            # As for the threads that are waiting for their tasks' starting times, we perform a notify_all on the
            # shared condition object
            self._sleepCondition.acquire()
            self._sleepCondition.notify_all()
            self._sleepCondition.release()
            # By default, all currently running subprocesses at the time of termination are killed
            if kill_abruptly:
                self._retry_tasks = False
                for t in self._threads:
                    t.force_stop_process()
            for i in range(len(self._threads)):
                self._threads[i].join()
                self._threads[i] = None
            self._initialized = False
            self._threads.clear()
            ThreadPool.logger.debug('Thread pool successfully stopped')

    def _execute_task(self, task):
        """
        Implementation of an abstract method. Performs the execution of a fault or benchmark, and communicates the
        outcome to all connected peers
        
        :param task: The task object, in this case a Task instantiation 
        """
        # The elapsed time since the start of the session is computed
        elapsed_time = time() - self._session_start_abs + self._correction_factor
        # The time that is left until the scheduled start of the task is computed, and we sleep until that time
        time_to_task = task.timestamp - self._session_start - elapsed_time
        if time_to_task > 0:
            self._sleepCondition.acquire()
            self._sleepCondition.wait(time_to_task)
            self._sleepCondition.release()
        # If the scheduled start time for the task has already passed (is expired) we can either skip it
        # (if skip_expired is True) or still start it immediately
        elif time_to_task < 0 and self._skip_expired:
            InjectionThreadPool.logger.warning('Starting time of task %s expired. Skipping' % task.args)
            self._process_result(task, time(), -1)
            return
        # We parse the arguments sequence for the command of the task, supplied as string in the message
        task_args = split(task.args, posix=self._posix_shell)
        task_duration = task.duration
        # If the task has no expected duration, no timeout is set
        task_timeout = task_duration if task_duration != Task.VALUE_DUR_NO_LIM else None
        task_end_time = None
        task_start_time = time()
        # We spawn a subprocess running the task with its arguments
        p = current_thread().start_process(args=task_args)
        if p is None and not current_thread().has_to_terminate():
            # If no subprocess was spawned even if the thread has not been flagged for termination, it means there
            # was an error
            InjectionThreadPool.logger.error('Error while starting task %s, check if path is correct', task.args)
            self._process_result(task, time(), -1)
            return
        elif p is None:
            # The thread may have been woken up because the pool must be terminated; in that case, we return
            return
        InjectionThreadPool.logger.info('Executing new task %s' % task.args)
        # All connected hosts are informed that the task has been started
        self._inform_start(task, task_start_time)
        rcode = 0
        try:
            # If there is no timeout for the task, we just wait for its termination and store its return code
            if task_timeout is None:
                p.wait(timeout=task_timeout)
                task_end_time = time()
                rcode = p.returncode
            else:
                # If there IS a timeout for the task, we wait for its termination
                while task_timeout > 0:
                    p.wait(timeout=task_timeout)
                    task_end_time = time()
                    rcode = p.returncode
                    # If the task terminates before its expected duration, and retry_tasks is True, we will create
                    # a new task identical to the first one: its timeout is the remaining time left for execution
                    # according to the original expected duration
                    task_timeout = task_duration - (task_end_time - task_start_time)
                    if self._retry_tasks and task_timeout > 0:
                        if rcode != 0:
                            InjectionThreadPool.logger.warning('Sub-task %s terminated unexpectedly' % task.args)
                        p = current_thread().start_process(args=task_args)
                    else:
                        break
        # If the task has not terminated by its timeout, we just kill the process and collect the result
        except TimeoutExpired:
            current_thread().force_stop_process()
            task_end_time = time()
            rcode = 0
        # All of the connected peers are informed of the termination of the task
        self._process_result(task, task_end_time, rcode)
        # Logging is done according to the return code of the task
        if rcode != 0:
            InjectionThreadPool.logger.error('Task %s terminated unexpectedly' % task.args)
        else:
            InjectionThreadPool.logger.info('Task %s terminated normally' % task.args)

    def _inform_start(self, task, timestamp):
        """
        Method that sends a broadcast message to all connected hosts when a task is started
        
        :param task: The msg related to the task that has been started
        :param timestamp: The timestamp related to the starting time
        """
        msg = MessageBuilder.status_start(task.args, task.duration, task.seqNum, timestamp, task.isFault)
        if msg is not None:
            self._server.broadcast_msg(msg)

    def _process_result(self, task, timestamp, rcode):
        """
        Method that sends a broadcast message to all connected hosts when a task terminates
        
        :param task: The msg related to the task that has terminated
        :param timestamp: The timestamp related to the termination time
        :param rcode: The return code of the task's execution
        """
        if rcode != 0:
            msg = MessageBuilder.status_error(task.args, task.duration, task.seqNum, timestamp, task.isFault, rcode)
        else:
            msg = MessageBuilder.status_end(task.args, task.duration, task.seqNum, timestamp, task.isFault)
        if msg is not None and not current_thread().has_to_terminate():
            self._server.broadcast_msg(msg)
