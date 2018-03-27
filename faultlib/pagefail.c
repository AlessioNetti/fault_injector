#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <signal.h>

char *prob_path = "/debug/fail_page_alloc/probability";
char *int_path = "/debug/fail_page_alloc/interval";
char *times_path = "/debug/fail_page_alloc/times";
char *order_path = "/debug/fail_page_alloc/min-order";
int interval = 5, low_prob = 25, hi_prob = 50, min_order = 0;

void echo_to_file(int val, char *path)
{
    FILE *out=NULL;
    char buf[256];
    snprintf(buf, 256, "%d", val);
    out = fopen(path, "w");
    fwrite(buf, sizeof(char), strlen(buf) + 1, out);
    fclose(out);
}

void signal_handler(int sig_number)
{
    if(sig_number == SIGINT || sig_number == SIGTERM)
    {
        echo_to_file(0, prob_path);
        echo_to_file(0, times_path);
        echo_to_file(0, int_path);
        echo_to_file(0, order_path);
        //printf("Exiting\n");
        exit(0);
    }
}

// This program injects page allocation failures through the Linux Fault Injection framework
int main (int argc, char *argv[])
 {
    char *end;
    int prob_to_set=0, duration=0;

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
            prob_to_set = low_prob;
        else
            prob_to_set = hi_prob;
    }

    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);

    echo_to_file(-1, times_path);
    echo_to_file(interval, int_path);
    echo_to_file(prob_to_set, prob_path);
    echo_to_file(min_order, order_path);

    sleep(duration);

    echo_to_file(0, prob_path);
    echo_to_file(0, times_path);
    echo_to_file(0, int_path);
    echo_to_file(0, order_path);

    return 0;
 }
