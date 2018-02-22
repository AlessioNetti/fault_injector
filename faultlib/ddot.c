#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <signal.h>
#include <time.h>
#include <math.h>

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
    char *end;
    int cache_size_base = 10240 * 1024, cache_size = 0, num_sizes = 3, num_rows = 0, size_now = 0;
    int i, j, k;
    float size_muls[] = {0.9f, 5.0f, 10.0f};
    double my_number = 0.0f, edge = 1e12, *mat1, *mat2, *mat3;
    int low_intensity = 1, high_intensity = 2;
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
            cache_size = cache_size_base * low_intensity;
        else
            cache_size =  cache_size_base * high_intensity;
    }

    srand(time(NULL));
    signal(SIGALRM, signal_handler);
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
    alarm(duration);

    //printf("Starting CPU and cache interference\n");
    while(1)
    {
        my_number = -edge + 2.0*edge*((rand() + 1.0)/RAND_MAX);
        num_rows = (int)floor(sqrt(cache_size * size_muls[size_now] / sizeof(double)));
        size_now = (size_now + 1) % num_sizes;
        mat1 = (double*)malloc(num_rows*num_rows*sizeof(double));
        mat2 = (double*)malloc(num_rows*num_rows*sizeof(double));
        mat3 = (double*)malloc(num_rows*num_rows*sizeof(double));
        if(mat1==NULL || mat2==NULL || mat3==NULL)
        {
            //printf("Allocation failed, exiting\n");
            return -1;
        }
        for(i=0;i<num_rows;i++)
            for(j=0;j<num_rows;j++)
                *(mat1 + i*num_rows + j) = my_number;
                *(mat2 + i*num_rows + j) = my_number;
        for(i=0;i<num_rows;i++)
            for(j=0;j<num_rows;j++)
            {
                *(mat3 + i*num_rows + j) = 0;
                for(k=0;k<num_rows;k++)
                    *(mat3 + i*num_rows + j) += *(mat1 + i*num_rows + k) * *(mat2 + k*num_rows + j);
            }
        free(mat1);
        free(mat2);
        free(mat3);
    }
    return 0;
 }