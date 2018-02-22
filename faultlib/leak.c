#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <signal.h>

int child_pid = 0, parent_pid = 0, child_status = 0;

void signal_handler(int sig_number)
{
    if(sig_number == SIGALRM)
    {
        if(child_pid != 0)
        {
            kill(child_pid, SIGKILL);
            wait(&child_status);
            //printf("Killing child\n");
        }
        exit(0);
    }
}

// This program generates a controlled memory leak
int main (int argc, char *argv[])
 {
    char *end, *reference_array = NULL, *my_array = NULL;
    int sleep_period = 2, i;
    int array_size_base = 1048576 * 10;
    int array_size = 0;
    int low_intensity = 4, high_intensity = 16;
    int duration = 0;

    if (argc <= 1)
    {
        //printf("Not enough arguments, exiting\n");
        return 0;
    }
    else
    {
        duration = (int)strtoll(argv[1], &end, 10);
        //printf("Starting with %i dur\n", duration);
        if(argc == 3 && strcmp(argv[2], "l") == 0)
            array_size = array_size_base * low_intensity;
        else
            array_size = array_size_base * high_intensity;
    }

    parent_pid = getpid();
    signal(SIGALRM, signal_handler);
    alarm(duration);

    reference_array = (char*)malloc(array_size * sizeof(char));
    for(i=0; i < array_size; i++)
        reference_array[i] = (char)((i + 57) % 26);

    while(1)
    {
        child_pid = fork();
        if(child_pid == 0)
        {
            //printf("Starting to flood memory\n");
            while(1)
            {
                my_array = (char*)malloc(array_size * sizeof(char));
                if(my_array == NULL || getppid() == parent_pid)
                    return 0;
                else
                    memcpy(my_array, reference_array, array_size);
                sleep(sleep_period);
            }
            return 0;
        }
        else
            wait(&child_status);
            child_pid = 0;
            //printf("Restarting child\n");
    }
    return 0;
 }