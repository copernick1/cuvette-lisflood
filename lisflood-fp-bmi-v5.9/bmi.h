/* -*- c-file-style: "stroustrup" -*- */
/* Please use the stroustrup coding standard: */


#ifndef BMI_API_H
#define BMI_API_H

#define BMI_API_VERSION_MAJOR 1
#define BMI_API_VERSION_MINOR 0

#if defined _WIN32
#define BMI_API __declspec(dllexport)
/* Calling convention, stdcall in windows, cdecl in the rest of the world */
#define CALLCONV __stdcall
#else
#define BMI_API
#define CALLCONV
#endif


#define MAXSTRINGLEN 1024
#define MAXDIMS 6
#include <stddef.h>

typedef enum {
    ALL,
    DEBUG,
    INFO,
    WARN,
    ERROR,
    FATAL
} Level;

#ifdef __cplusplus
extern "C" {
#endif

    /* control functions. These return an error code. */
    BMI_API int initialize(const char *config_file);

    BMI_API int update();

    BMI_API int update_until(double t);

    BMI_API int finalize();

    /* time control functions */
    BMI_API int get_start_time(double *t);

    BMI_API int get_end_time(double *t);

    BMI_API int get_current_time(double *t);

    BMI_API int get_time_step(double *dt);

    BMI_API int get_time_units(char *units);

    /* variable info */
    BMI_API int get_var_shape(const char *name, int shape[MAXDIMS]);

    BMI_API int get_var_rank(const char *name, int *rank);

    BMI_API int get_var_type(const char *name, char *type);

    BMI_API int get_var_units(const char *name, char *units);

    BMI_API int get_var_stride(const char *name, int *stride);

    BMI_API int get_var_itemsize(const char *name, int *size);

    BMI_API int get_var_nbytes(const char *name, int *nbytes);

    BMI_API int get_input_var_name_count(int *count);

    BMI_API int get_output_var_name_count(int *count);

    BMI_API int get_input_var_names(char **names);

    BMI_API int get_output_var_names(char **names);

    /* get values */
    BMI_API int get_value(const char *name, void *dest);

    BMI_API int get_value_ptr(const char *name, void **dest);

    BMI_API int get_value_at_indices(const char *name, void *dest, int *indices, int count);

    /* set values */
    BMI_API int set_value(const char *name, const void *src);

    BMI_API int set_value_at_indices(const char *name, int *indices, int count, const void *src);

    /* model info */
    BMI_API int get_component_name(char *name);

    /* logger to be set from outside so we can log messages */
    typedef void (CALLCONV *Logger)(Level level, const char *msg);

    /* set logger by setting a pointer to the log function */
    BMI_API void set_logger(Logger logger);

#ifdef __cplusplus
}
#endif

#endif
