#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <signal.h>

FILE *in=NULL, *out=NULL;
char *file_name = "injection_temp_file";
char *my_string = "FLOODING_THE_FILESYSTEM\nFLOODING_THE_FILESYSTEM\nFLOODING_THE_FILESYSTEM\nFLOODING_THE_FILESYSTEM\n"
                  "FLOODING_THE_FILESYSTEM\nFLOODING_THE_FILESYSTEM\nFLOODING_THE_FILESYSTEM\nFLOODING_THE_FILESYSTEM\n"
                  "FLOODING_THE_FILESYSTEM\nFLOODING_THE_FILESYSTEM\n";

void signal_handler(int sig_number)
{
    if(sig_number == SIGALRM || sig_number == SIGINT)
    {
        if(in != NULL)
        {
            fclose(in);
            remove(file_name);
        }
        else if(out != NULL)
        {
            fclose(out);
            remove(file_name);
        }
        //printf("Exiting\n");
        exit(0);
    }
}

// This program generates interference on the ALU by performing floating-point operations
int main (int argc, char *argv[])
 {
    int file_size_base = 1048576, file_size = 0, my_len = 0, num_done = 0, buf_len = 2048, i;
    char *end, buffer[buf_len];
    int low_intensity = 1, high_intensity = 2;
    int duration = 0, sleep_period = 2;

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
            file_size = file_size_base * low_intensity;
        else
            file_size =  file_size_base * high_intensity;
    }

    my_len = strlen(my_string);
    signal(SIGALRM, signal_handler);
    signal(SIGINT, signal_handler);
    alarm(duration);

    //printf("Starting Disk IO interference\n");
    while(1)
    {
        out = fopen(file_name, "w");
        for(i=0;i<file_size;i++)
        {
            num_done = fwrite(my_string, sizeof(char), my_len, out);
            if(num_done == 0)
                break;
        }
        fclose(out);
        //printf("Done writing\n");
        out = NULL;
        sleep(sleep_period);
        in = fopen(file_name, "r");
        do
        {
            num_done = fread(buffer, sizeof(char), buf_len, in);
        }
        while(num_done > 0);
        fclose(in);
        //printf("Done reading\n");
        in = NULL;
        sleep(sleep_period);
    }
    return 0;
 }