#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <signal.h>
#include <time.h>
#include <math.h>

// This anomaly program is inspired by the "ddot" anomaly described in the ISC-HPC 2017 paper by Tuncer et al.
// "Diagnosing Performance Variations in HPC Applications Using Machine Learning", pp. 355-373, Springer.

void signal_handler(int sig_number)
{
    if(sig_number == SIGALRM || sig_number == SIGINT || sig_number == SIGTERM)
    {
        //printf("Exiting\n");
        exit(0);
    }
}

double** get_mat(int rows, int columns, double val, int reuse)
{
    int i,j;
    double **mainp = NULL, *p;
    mainp = (double**)malloc(rows*sizeof(double));
    if(mainp == NULL)
        return NULL;
    for(i=0; i<rows; i++)
    {
        if(i==0 || reuse==0)
        {
            mainp[i] = (double*)malloc(columns*sizeof(double));
            for(j=0;j<columns;j++)
                mainp[i][j] = val;
        }
        else
            mainp[i] = mainp[0];
    }
    return mainp;
}

void free_mat(double** mat, int rows, int reuse)
{
    int i;
    if(reuse==0)
        for(i=0; i<rows; i++)
            free(mat[i]);
    else
        free(mat[0]);
    free(mat);
}

// This program generates interference on the ALU by performing floating-point operations
int main (int argc, char *argv[])
 {
    char *end;
    int cache_size = 0, num_sizes = 3, num_rows = 0, reuse=1;
    int i, j, k, d1, d2;
    int cache_sizes_base[] = {16 * 1024, 128 * 1024, 10240 * 1024};
    float size_muls[] = {0.9f, 5.0f, 10.0f};
    double my_number = 0.0f, total=0.0f, edge = 1e12, **mat1, **mat2;
    int low_intensity = 1, high_intensity = 2, intensity = 0;
    int duration = 0;

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
            intensity = low_intensity;
        else
            intensity = high_intensity;
    }

    srand(time(NULL));
    signal(SIGALRM, signal_handler);
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
    alarm(duration);

    //printf("Starting CPU and cache interference\n");
    while(1)
    {
        for(d1=0; d1<num_sizes; d1++)
            for(d2=0; d2<num_sizes; d2++)
            {
                my_number = -edge + 2.0*edge*((rand() + 1.0)/RAND_MAX);
                cache_size = cache_sizes_base[d1] * size_muls[d2] * intensity;
                num_rows = (int)floor(sqrt(cache_size / sizeof(double)));
                mat1 = get_mat(num_rows, num_rows, my_number, reuse);
                mat2 = get_mat(num_rows, num_rows, my_number * 2, reuse);
                if(mat1==NULL || mat2==NULL)
                {
                    //printf("Allocation failed, exiting\n");
                    return -1;
                }
                total = 0.0f;
                for(i=0; i<num_rows; i++)
                    for(j=0; j<num_rows; j++)
                        for(k=0; k<num_rows; k++)
                            //We suppose mat2 is transposed
                            total += mat1[i][k] * mat2[j][k];
                free_mat(mat1, num_rows, reuse);
                free_mat(mat2, num_rows, reuse);
            }
    }
    return 0;
 }