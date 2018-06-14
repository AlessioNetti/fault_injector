# FINJ Fault Injection Tool

FINJ is an open-source Python tool for **fault injection** targeted at HPC systems. It works in Python 3.4 and above, without any platform restriction. FINJ can be seamlessly integrated with other injection tools targeted at specific fault types, thus enabling users to coordinate faults from different sources and different system levels. FINJ also provides *workload* support, thus permitting users to specify lists of applications to be executed and faults to be triggered on multiple nodes at specific times with specific durations. FINJ represents a high-level, flexible tool, enabling users to perform complex and reproducible experiments, aimed at revealing the relations that may exist between faults, application behavior and the system itself.
Fault injection in FINJ is achieved through tasks that are executed on target nodes: each task corresponds to a particular application, which can either be a benchmark program or a fault-triggering program. This approach allows for great flexibility, as FINJ can be integrated with any type of low-level fault injection tool. The process of fault injection in FINJ is orchestrated by two entities, which communicate through a simple message protocol via TCP sockets:

* A fault injection **engine**: runs on hosts that are the target of injection, and manages the execution of all tasks related to faults and benchmarks;
* A fault injection **controller**: runs on a separate orchestrator host, and instructs controllers on which tasks should be run, and when. Controllers also collect and store all output produced by engines.

Workloads in FINJ are structured as CSV files containing entries for tasks that must be executed at specific times and with specific durations. A particular execution of a FINJ workload constitutes an **injection session**.

 ## Table of Contents

  * [Getting Started](#getting-started)
    * [Starting Controller Instances](#starting-controller-instances)
    * [Starting Engine Instances](#starting-engine-instances)
  * [Tasks and Workloads](#tasks-and-workloads)
    * [Tasks in FINJ](#tasks-in-finj)
    * [Workload Generation](#workload-generation)
    * [Output Data](#output-data)
  * [Configuration](#configuration)
    * [Controller-only Options](#controller-only-options)
    * [Engine-only Options](#engine-only-options)
    * [Generic Options](#generic-options)
  * [Miscellaneous Info](#miscellaneous-info)

## Getting Started

You can install FINJ by simply cloning the repository. Everything you need to get up and running is included. There are no external Python dependencies, except for the *scikit-learn*, *scipy* and *numpy* libraries, in case you wish to use the *workload_generator* and *post_processing* packages.  Launch scripts are supplied with FINJ in order to start and configure engine and controller instances. These scripts are **finj_controller.py** and **finj_engine.py**.

### Starting Controller instances

FINJ controllers should be executed on nodes that are not subject to injection sessions, and will orchestrate such process on target nodes. The controller maintains connections to all nodes involved in the injection session, which run fault injection engine instances and whose addresses are specified by users when launching the program. Therefore, injection sessions can be performed on multiple nodes at the same time. The controller reads task entries from the selected workload: the reading process is incremental, and tasks are read in real-time a few minutes before their expected execution, according to their relative timestamp. For each task the controller sends a command to all target hosts, instructing them to start the new task at the specified time. Finally, the controller collects all status messages produced by the target hosts, and stores them in a separate file for each host.

The **finj_controller.py** script allows to configure and start controller instances. Its syntax is the following:

```
python finj_controller.py [ -s ] [ -c CONFIG ] [ -w WORKLOAD ] [ -a ADDRESSLIST ] [ -m MAXTASKS ]
```

Its optional arguments are the following:

* **-s**: Enables silent mode. In this mode, all logging messages are suppressed, except for errors;
* **-c**: Supplies the path to a JSON configuration file for the controller. If none is specified, the controller will use a default configuration;
* **-w**: Contains the path to a CSV workload file to be injected in target hosts. If none is supplied, the controller will connect in *listening* mode, collecting all data produced by engines but without injecting any workload;
* **-a**: Contains the list of addresses of hosts running engine instances that will be the target of injection. The addresses are supplied as comma-separated *< ip >:< port >* pairs. If this argument is not supplied, the script will search for valid addresses in the supplied configuration file. If none is found, the controller aborts;
* **-m**: Specified a maximum limit for the number of tasks to be injected from the specified workload.


### Starting Engine instances

FINJ engines should be started  on nodes that will be subject  to fault injection. The engine is structured as a daemon, and is perpetually running. The engine waits for task commands to be received from remote controller instances: these commands are accepted from only one controller at a time, which is defined as the *master* of the injection session. The engine manages received task commands by assigning them to a dedicated thread from a pool. The thread manages all aspects related to the execution of the task, such as spawning the necessary subprocesses and sending status messages to controllers when relevant events (such as the start or termination of the task) occur.

The **finj_engine.py** script allows you to configure and start engine daemons on target nodes. Its syntax is the following:

```
python finj_engine.py [ -c CONFIG ] [ -p PORT ]
```

Its optional arguments are the following:

* **-c**: Supplies the path to a JSON configuration file for the controller. If none is specified, the controller will use a default configuration;
* **-p**: The port that will be used for listening to remote controller requests.

## Tasks and Workloads

In order to inject faults in your system, you first need to understand how FINJ treats tasks, and how you can generate workloads.

### Tasks in FINJ

Fault injection in FINJ is achieved through the use of tasks. A task is a subprocess, which may be related to a fault-triggering program or to a benchmark application, and is managed by the FINJ thread pool. A task has several attributes:

* **args**: String. The full shell command required to run the task. Be aware that the arguments must refer to a path or command that is reachable by the host on which the engine is running. It is advisable to use absolute paths;
* **timestamp**: Integer. The relative timestamp at which the task must be started. In general, the first task in a workload has a timestamp of 0, and all of the subsequent ones have increasing timestamps. Then, when the injection session is started, the controller maps the relative timestamp of the first task to the absolute timestamp, and syncs with the target hosts;
* **duration**: Integer. The duration of the task in seconds. If the *RETRY_TASKS* option is disabled (see below) the duration is to be considered as an upper bound: if the task terminates before its expected duration, it will be finalized. If it exceed the limit set by the duration, it will be terminated by FINJ. If the *RETRY_TASKS* option is instead enabled, tasks will be restarted whenever they terminate before their expected duration, in order to last for that exact duration. If the duration is set to 0, the task is always allowed to run until its termination, and is then finalized;
* **isFault**: Boolean. Determines whether the task is a fault-triggering program or a benchmark;
* **seqNum**: Integer. A unique sequence number used to identify the task. This will likely change in the future;
* **cores**: String. The list of CPU cores that the task is allowed to use on target hosts, enforced through a NUMA Control policy with the *physcpubind* option of the *numactl* command. The syntax is the same as for the *numactl* command, but using explicit lists of cores (i.e. '0,1,2,3,4,5' instead of '0-5') is advised; this attribute is optional.

You can find many examples of fault programs in the *faultlib* subdirectory of this repository, that you are free to use. These programs are written in C, and they will trigger various adverse effects on your system.

### Workload Generation

 In FINJ, tasks to be injected in a system are grouped in workloads. A FINJ workload is a CSV file, in which each entry corresponds to a task to be executed at a specific time. Tasks have all the attributes presented earlier. A simple example of workload is the following:

```
timestamp;duration;seqNum;isFault;cores;args
0;1719;1;False;0;./hpl lininput
587;291;2;True;0;./leak 291 l
1171;244;3;True;0;sudo ./cpufreq 244
```

In this case, the workload is composed of three tasks, of which the first is a benchmark, and the other two are fault-triggering programs. All tasks are executed on core 0 of the target host.  As you can see, writing workloads for FINJ is extremely easy, and can be done by hand whenever you want to trigger extremely specific anomalous conditions. For more general use, we supply a **workload generator** for use with FINJ (*workload_generator* package). When using the workload generator, you will need to define a few things:

* The  **time span** of your workload and/or the maximum number of tasks;
* The list of benchmark and fault-triggering **commands** to be used to generate tasks;
* **Distributions** for inter-arrival times and durations of tasks. These are separated for fault and benchmark tasks, for a total of four distributions. We supply methods to automatically set these distributions, if you don't want to mess with them.

The workload generator will then generate a workload with the statistical features imposed by the distributions, and with the requested size. There are many more parameters for the workload generator; to know more about them, please refer to the documentation and to the examples (*workload_gen_example* and *worklad_fit_example*) contained in the package.
When generating a workload, the tool will generate a *probe* file as well: this file contains exactly one entry for each command that was supplied, and all tasks have a very short duration. The probe is useful to test whether all tasks can be correctly executed on target hosts, before starting longer injection sessions.

### Output Data

Data collection and output in FINJ is performed by controllers. Also, results for different target hosts of an injection session will be written to separate files.
The main output of FINJ contains records for relevant events that occur in target hosts during the injection session, and is in CSV format. The following is a sample output for the workload presented earlier:

```
timestamp;type;args;seqNum;duration;isFault;cores;error
1522524987;command_session_s;None;None;None;None;None;None
1522525007;status_start;./hpl lininput;1;1719;False;0;None
1522525594;status_start;./leak 291 l;2;291;True;0;None
1522525885;status_end;./leak 291 l;2;291;True;0;None
1522526178;status_start;sudo ./cpufreq 244;3;244;True;0;None
1522526422;status_end;sudo ./cpufreq 244;3;244;True;0;None
1522526726;status_end;./hpl lininput;1;1719;False;0;None
1522526727;command_session_e;None;None;None;None;None;None
```

The fields are the same as seen for the workload files. There are however a few differences:

* The **timestamp** field here represents the absolute timestamp in the target host at which the event occurred;
* There is an **error** field which contains error codes, when encountered.

Most importantly, the **type** field defines the specific type of the occurred event. These are the following types:

* **command_session_s** and **command_session_e**: they indicate the successful start and termination of an injection session:
* **status_start**, **status_end** and **status_restart** indicate that a task was successfully started, finalized or restarted;
* **status_err** indicates that a task terminated with an error and could not be restarted;
* **detected_lost** and **detected_restore** are controller-side events, meaning that connection with the target host was either lost or re-established;
* **status_reset** indicates that, for some reason, the thread pool in the target host was reset, and thus all previously running tasks were lost. This can happen when controllers re-establish connection with engines that have the *RECOVER_AFTER_DISCONNECT* option disabled.

Post-processing of the data is easy, and the output files can be interpreted with ease. If the *LOG_OUTPUTS* option is enabled on engine instances, controllers will also store all output produced by tasks in separate plain-text files.


## Configuration

FINJ can be extensively configured through the use of JSON configuration files. There are different options for engine and controller instances. Two sample configuration files (engine.config and controller.config) are supplied in the config subdirectory. We will now see which are the available configuration options for the tool.

### Controller-only options

* **RESULTS_DIR**:  String. Path of the directory in which all output is stored. Default is  *'results'*;
* **PRE_SEND_INTERVAL**:  Integer. Represents the interval (in seconds) between the issuing of a task execution command by a controller, and its execution by an engine. A value of 0 means that controllers will issue task commands at the exact time of their expected execution. A value lower than 0 means that controller will send all task command simultaneously; these will then be queued by engines, and executed at due time. Default is 600;
* **WORKLOAD_PADDING**: Integer. Represents a padding value (in seconds) before the first task of the workload is started. Default is 20;
* **SESSION_WAIT**: Integer. Represents the maximum time (in seconds) for which the controller waits to receive an *ack* from engine instances to which it has sent an injection session start request, before disconnecting. Default is 60;
* **RETRY_INTERVAL**: Integer. Represents the time interval (in seconds) for which controllers will try to re-establish connections to engines that have been lost. If 0, controllers will never try to re-connect. Default is 600;
* **RETRY_PERIOD**: Integer. Represents the time interval (in seconds) between one re-connection attempt and the other, when engine hosts are temporarily lost. Default is 30;
* **HOSTS**: List of strings. Contains the list of hosts in *< ip >:< port >* pairs, running engine instances, to which the controller must connect at startup. Default is *[]*.

### Engine-only options

* **SERVER_PORT**: Integer. Defines the listening port for the engine instance. Default is 30000;
* **MAX_REQUESTS**: Integer. Defines the number of worker threads in the thread pool, and thus the maximum number of concurrent tasks. Default is 20;
* **SKIP_EXPIRED**: Boolean. If *True*, tasks whose execution commands have arrived after their expected execution time are discarded. Otherwise, they are executed anyway. Default is *True*;
* **RETRY_TASKS**: Boolean. If *True*, tasks that terminate before their expected duration are restarted in order to reach that specific duration. If *False*, the task is simply finalized. Default is *True*;
* **RETRY_TASKS_ON_ERROR"**: Boolean. If *True*, and if *RETRY_TASKS* is also *True*, tasks that terminate with errors (return code != 0) will also be restarted when they do not reach their expected duration. If *False*, these tasks are simply finalized. PAY ATTENTION: you should set this option to *False* when you are not sure whether the tasks you are running will work or not. Default is *True*;
* **ABRUPT_TASK_KILL**: Boolean. If *True*, tasks that must be terminated when the engine is being shut down will be terminated immediately and not restarted to reach their expected duration. Otherwise, they are allowed to last until their expected duration. Default is *True*;
* **ENABLE_ROOT**: Boolean. If *True*, tasks requiring superuser rights are allowed to run. Note that in order for this to work, you must enable password-less root access on the machine the engine is running on, for the tasks that need it. Default is *False*;
* **LOG_OUTPUTS**: Boolean. If *True*, engines will collect all output that is printed to the standard output and standard error channels by tasks. Such output is then forwarded to controllers, which will store it in separate files for each task. Default is *True*;
* **NUMA_CORES_FAULTS**: String. Represents the list of CPU core IDs that are allowed for use by fault tasks null. The syntax is that of NUMA Control policies (see *physcpubind* option of *numactl* command). If set to a specific value, this configuration will always override that contained in task execution commands. If set to *'all'*, then tasks will be bound to the CPU cores indicated in their execution commands. Finally, if set to *null*, *numactl* CPU binding is disabled altogether. Default is *null*;
* **NUMA_CORES_BENCHMARKS**: String. Same as *NUMA_CORES_FAULTS*, but applies to benchmark tasks. Default is  *null*.

### Generic options

* **RECOVER_AFTER_DISCONNECT**: Boolean. If *True*, engines and/or controllers will attempt to recover the previous injection session state when connection is re-established after a temporary loss. If applied to **Controllers**, these will try to re-send all task execution commands that were lost during the connection loss window. Otherwise, these tasks are considered as lost. If applied to **Engines**, these will preserve tasks that were running on the system when the controller re-connects to the engine, requiring the controller to identify itself as the previous session master. Otherwise, the engine will terminate all tasks that were running previously to re-connection, and reset the thread pool.  Default is *False* for both controllers and engines;
* **AUX_COMMANDS**: List of strings. Contains a list of shell commands corresponding to tasks that must be launched alongside FINJ and terminated with it. A practical example is a system monitoring framework (such as *LDMS*) which can be launched together with an injection session to collect useful data about system behavior. Default is *[]* for both controllers and engines.

## Miscellaneous Info

* The **post_processing** package is not part of the core FINJ distribution, and is here for demonstrative purposes. It contains scripts and algorithms to perform machine learning-based fault detection by using system performance metrics collected with the LDMS framework. You are free to use it, however do not expect anything clean and bug-free;
* If you wish to know more about FINJ, please refer to the documentation and to our reference **paper**, *"FINJ: A Fault Injection Tool for HPC Systems"*, written by Alessio Netti et al.

## Authors

* **Alessio Netti** - [AlessioNetti](https://github.com/AlessioNetti)

See also the list of [contributors](https://github.com/AlessioNetti/fault_injector/graphs/contributors) who participated in this project.

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details  .

## Acknowledgments

* Developed in the Department of Computer Science and Engineering (DISI) of the University of Bologna.