#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <signal.h>
#include <math.h>
#include <time.h>

#define PI 3.1415926

void signal_handler(int sig_number)
{
    if(sig_number == SIGALRM || sig_number == SIGINT || sig_number == SIGTERM)
    {
        //printf("Exiting\n");
        exit(0);
    }
}

// This program generates interference on the ALU by performing floating-point operations
int main (int argc, char *argv[])
 {
    time_t start;
    char *end;
    double my_number = 0.0f, edge = 1e12;
    struct timespec tim, tim2;
    int num_ops = 1000000, i;
    int low_intensity = 0, sleep_period = 1;
    int duration = 0;
    tim.tv_sec = 0;
    tim.tv_nsec = 500000000L;
    if (argc <= 1)
    {
        //printf("Not enough arguments, exiting\n");
        return -1;
    }
    else
    {
        duration = (int)strtoll(argv[1], &end, 10);
        //printf("Starting with %i dur\n", duration);
        if(argc == 3 && strcmp(argv[2], "l") == 0)
            low_intensity = 1;
    }

    srand(time(NULL));
    signal(SIGALRM, signal_handler);
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
    alarm(duration);

    //printf("Starting ALU interference\n");
    start = time(NULL);
    while(1)
    {
        my_number = -edge + 2.0*edge*((rand() + 1.0)/RAND_MAX);
        for(i=0;i<num_ops;i++)
        {
            my_number -= my_number * 3.0 * PI;
            my_number += my_number * 6.4 * PI;
            my_number = pow(my_number, 2.0);
            my_number = sqrt(my_number);
            my_number = log(my_number);
            my_number = exp(my_number);
        }
        if(low_intensity == 1 && time(NULL)-start > sleep_period)
        {
            nanosleep(&tim, &tim2);
            start = time(NULL);
        }
    }
    return 0;
 }