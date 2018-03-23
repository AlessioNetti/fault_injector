#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <signal.h>

char *pstate_path = "/sys/devices/system/cpu/intel_pstate/max_perf_pct";
int perf_pstate=100, ps_pstate=50, ps_pstate_low=70;

void set_pstate(int new_pstate)
{
    FILE *out=NULL;
    char buf[256];
    snprintf(buf, 256, "%d", new_pstate);
    out = fopen(pstate_path, "w");
    fwrite(buf, sizeof(char), strlen(buf) + 1, out);
    fclose(out);
}

void signal_handler(int sig_number)
{
    if(sig_number == SIGINT || sig_number == SIGTERM)
    {
        set_pstate(perf_pstate);
        //printf("Exiting\n");
        exit(0);
    }
}

// This program reduces the performance of the CPU by decreasing its clock frequency
int main (int argc, char *argv[])
 {
    char *end;
    int pstate_to_set=0, duration=0;

    if(geteuid() != 0)
    {
        //printf("This program must be run as root, exiting\n");
        return -1;
    }
    if (argc <= 1)
    {
        //printf("Not enough arguments, exiting\n");
        return -1;
    }
    else
    {
        duration = (int)strtoll(argv[1], &end, 10) + 300;
        //printf("Starting with %i dur\n", duration);
        if(argc == 3 && strcmp(argv[2], "l") == 0)
            pstate_to_set = ps_pstate_low;
        else
            pstate_to_set = ps_pstate;
    }

    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);

    set_pstate(pstate_to_set);
    sleep(duration);
    set_pstate(perf_pstate);

    return 0;
 }


// BELOW IS THE OLD PYTHON IMPLEMENTATION
/*
from os.path import isdir
from os import geteuid
from time import sleep
import signal, sys


perf_pstate = '100'
ps_pstate = '50'
ps_pstate_low = '70'


def signal_handler(signum, frame):
    if signum == signal.SIGINT or signum == signal.SIGTERM:
        set_pstate(perf_pstate)
        exit(0)


def set_pstate(new_pstate):
    pstate_path = '/sys/devices/system/cpu/intel_pstate/max_perf_pct'
    try:
        pstate_file = open(pstate_path, 'w')
        pstate_file.write(new_pstate)
        pstate_file.close()
    except Exception:
        print("Exception while changing P-State. Aborting...")
        exit(-1)


if __name__ == '__main__':
    low_int = False
    if geteuid() != 0:
        print('This script must be run as superuser.')
        exit(-1)
    if not isdir('/sys/devices/system/cpu/intel_pstate'):
        print('Frequency scaling is not available on this system.')
        exit(-1)
    if len(sys.argv) < 2 or int(sys.argv[1]) <= 0:
        print('Not enough arguments.')
        exit(-1)
    elif len(sys.argv) == 3 and sys.argv[2] == 'l':
        low_int = True
    duration = int(sys.argv[1])
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    set_pstate(ps_pstate if not low_int else ps_pstate_low)
    sleep(duration)
    set_pstate(perf_pstate)

    exit(0)


# BELOW IS THE VERSION FOR NON-INTEL CPUS

#perf_gov = 'performance'
#ps_gov = 'powersave'
#cpu_start = 0
#cpu_end = 16


#def signal_handler(signum, frame):
#    if signum == signal.SIGINT or signum == signal.SIGTERM:
#        set_governor(perf_gov, cpu_start, cpu_end)
#        exit(0)


#def set_governor(gov_name, cpu_start, cpu_end):
#    base_path = '/sys/devices/system/cpu/'
#    cpu_id = 'cpu'
#    governor_file = '/cpufreq/scaling_governor'
#    for i in range(cpu_start, cpu_end):
#        core_path = base_path + cpu_id + str(i) + governor_file
#        try:
#            gov_file = open(core_path, 'w')
#            gov_file.write(gov_name)
#            gov_file.close()
#        except Exception:
#            print("Exception while changing governor. Aborting...")
#            exit(-1)

#if __name__ == '__main__':
#    if geteuid() != 0:
#        print('This script must be run as superuser.')
#        exit(-1)
#    if not isdir('/sys/devices/system/cpu/cpu0/cpufreq/'):
#        print('Frequency scaling is not available on this system.')
#        exit(-1)
#    if len(sys.argv) < 2 or int(sys.argv[1]) <= 0:
#        print('Not enough arguments.')
#        exit(-1)
#
#    duration = int(sys.argv[1])
#    signal.signal(signal.SIGINT, signal_handler)
#    signal.signal(signal.SIGTERM, signal_handler)
#
#    set_governor(ps_gov, cpu_start, cpu_end)
#    sleep(duration)
#    set_governor(perf_gov, cpu_start, cpu_end)
#
#    exit(0)
*/
