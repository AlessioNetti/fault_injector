#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <signal.h>
#include <time.h>


void signal_handler(int sig_number)
{
    if(sig_number == SIGALRM || sig_number == SIGINT || sig_number == SIGTERM)
    {
        //printf("Exiting\n");
        exit(0);
    }
}

// This program only sleeps and does not inject any fault. Used to quantify detection bias.
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
        duration = (int)strtoll(argv[1], &end, 10) + 300;
        //printf("Starting with %i dur\n", duration);
        if(argc == 3 && strcmp(argv[2], "l") == 0)
            low_intensity = 1;
    }

    srand(time(NULL));
    signal(SIGALRM, signal_handler);
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
    alarm(duration);

    //printf("Going to sleep\n");
    sleep(duration);
    return 0;
 }