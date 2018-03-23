#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <time.h>
#include <signal.h>

int child_pid = 0, parent_pid = 0, child_status = 0;

void signal_handler(int sig_number)
{
    if(sig_number == SIGALRM || sig_number == SIGINT || sig_number == SIGTERM)
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
    char *end;
    int *my_array = NULL;
    int sleep_period = 2, num_iter = 10, i, j, k;
    int array_size_base = 1048576 * 18;
    int array_size = 0, array_size_old = 0;
    int low_intensity = 1, high_intensity = 2;
    int r, tot=0, duration = 0;

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
            array_size_base = array_size_base * low_intensity;
        else
            array_size_base = array_size_base * high_intensity;
        array_size = array_size_base;
    }

    parent_pid = getpid();
    srand(time(NULL));
    signal(SIGALRM, signal_handler);
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
    alarm(duration);

    while(1)
    {
        child_pid = fork();
        if(child_pid == 0)
        {
            srand(time(NULL));
            my_array = (int*)malloc(array_size * sizeof(int));
            for(i=0; i < array_size; i++)
                my_array[i] = (int)rand();
            //printf("Starting to saturate memory bandwidth\n");
            for(j=0; j<num_iter; j++)
            {
                array_size_old = array_size;
                array_size += array_size_base;
                my_array = (int*)realloc(my_array, array_size * sizeof(int));
                if(my_array == NULL || getppid() != parent_pid)
                {
                    //printf("Null array returned\n");
                    return -1;
                }
                else
                    for(i=0;i<array_size-array_size_old;i++)
                        my_array[array_size_old + i] = my_array[i];
                        for (k = 0; k < 10; k++)
                        {
                            r = rand();
                            if (r < array_size)
                                tot += my_array[r];
                        }
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