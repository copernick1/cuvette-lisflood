#include <cstdio>
#include <string>
#include <sstream>
#include <vector>
#include <algorithm>
#include <cstring>
#include "bmi.h"
#include "lisflood.h"
#include "global.h"
#include "initialize.h"
#include "update.h"
#include "finalize.h"

// List of variables exposed via BMI
static const std::vector<std::string> input_var_names = {
    "water depth",
    "water surface elevation",
    "qx",
    "qy",
    "rain",
    "n"
};

static const std::vector<std::string> output_var_names = {
    "water depth",
    "water surface elevation",
    "qx",
    "qy",
    "dem"
};

enum VARIABLE_LABEL {
    WATER_DEPTH,
    WATER_SURFACE_ELEVATION,
    QX,
    QY,
    RAIN,
    N,
    DEM,
    NOVAR
};

VARIABLE_LABEL variable2label(const std::string& variable) {
    if (variable == "water depth" || variable == "H") return WATER_DEPTH;
    if (variable == "water surface elevation") return WATER_SURFACE_ELEVATION;
    if (variable == "qx" || variable == "Qx") return QX;
    if (variable == "qy" || variable == "Qy") return QY;
    if (variable == "rain") return RAIN;
    if (variable == "n" || variable == "Manningsn") return N;
    if (variable == "dem" || variable == "DEM") return DEM;
    return NOVAR;
};

/* Store callback */
Logger logger = NULL;

/* Logger function */
void _log(Level level, std::string msg) {
    if (logger != NULL) {
        logger(level, msg.c_str());
    }
}

extern "C" int init(int, const char*[]);
extern "C" int init_iterateq();

extern "C" {

BMI_API int initialize(const char *config_file) {
    const char * argv[] = {"bmi", "-v", config_file};
    int result = init(3, argv);
    init_iterateq();
    return (result == 0) ? 0 : 1;
}

BMI_API int update() {
    iterateq_step();
    return 0;
}

BMI_API int update_until(double t) {
    while (Solverptr->t < t) {
        iterateq_step();
    }
    return 0;
}

BMI_API int finalize() {
    final_iterateq();
    final();
    return 0;
}

BMI_API int get_start_time(double *t) {
    *t = 0.0;
    return 0;
}

BMI_API int get_end_time(double *t) {
    *t = Solverptr->Sim_Time;
    return 0;
}

BMI_API int get_current_time(double *t) {
    *t = Solverptr->t;
    return 0;
}

BMI_API int get_time_step(double *dt) {
    *dt = Solverptr->Tstep;
    return 0;
}

BMI_API int get_time_units(char *units) {
    strcpy(units, "s");
    return 0;
}

BMI_API int get_var_type(const char *name, char *type) {
    VARIABLE_LABEL label = variable2label(name);
    if (label == NOVAR) return 1;
    strcpy(type, "double");
    return 0;
}

BMI_API int get_var_units(const char *name, char *units) {
    VARIABLE_LABEL label = variable2label(name);
    switch (label) {
        case WATER_DEPTH:
        case WATER_SURFACE_ELEVATION:
        case DEM:
            strcpy(units, "m"); break;
        case QX:
        case QY:
            strcpy(units, "m2 s-1"); break;
        case RAIN:
            strcpy(units, "m s-1"); break;
        default:
            strcpy(units, "-"); break;
    }
    return 0;
}

BMI_API int get_var_rank(const char *name, int *rank) {
    VARIABLE_LABEL label = variable2label(name);
    if (label == NOVAR) return 1;
    *rank = 2;
    return 0;
}

BMI_API int get_var_shape(const char *name, int shape[MAXDIMS]) {
    VARIABLE_LABEL label = variable2label(name);
    if (label == NOVAR) return 1;
    shape[0] = Parptr->ysz;
    shape[1] = Parptr->xsz;
    return 0;
}

BMI_API int get_var_stride(const char *name, int *stride) {
    VARIABLE_LABEL label = variable2label(name);
    if (label == NOVAR) return 1;
    stride[0] = Parptr->xsz;
    stride[1] = 1;
    return 0;
}

BMI_API int get_var_itemsize(const char *name, int *size) {
    *size = sizeof(double);
    return 0;
}

BMI_API int get_var_nbytes(const char *name, int *nbytes) {
    int shape[MAXDIMS];
    get_var_shape(name, shape);
    *nbytes = shape[0] * shape[1] * sizeof(double);
    return 0;
}

BMI_API int get_input_var_name_count(int *count) {
    *count = (int)input_var_names.size();
    return 0;
}

BMI_API int get_output_var_name_count(int *count) {
    *count = (int)output_var_names.size();
    return 0;
}

BMI_API int get_input_var_names(char **names) {
    for (size_t i = 0; i < input_var_names.size(); ++i) {
        strcpy(names[i], input_var_names[i].c_str());
    }
    return 0;
}

BMI_API int get_output_var_names(char **names) {
    for (size_t i = 0; i < output_var_names.size(); ++i) {
        strcpy(names[i], output_var_names[i].c_str());
    }
    return 0;
}

BMI_API int get_value_ptr(const char *name, void **dest) {
    VARIABLE_LABEL label = variable2label(name);
    switch (label) {
        case WATER_DEPTH: *dest = (void*)(Arrptr->H); break;
        case WATER_SURFACE_ELEVATION: {
             // WSE = H + DEM. Lisflood doesn't store WSE directly usually.
             // For pointer access, this is tricky. BMI says ptr should point to internal data.
             // If not available, maybe return error or provide a buffer?
             // But Lisflood actually has a WSE-like concept.
             return 1;
        }
        case QX: *dest = (void*)(Arrptr->Qx); break;
        case QY: *dest = (void*)(Arrptr->Qy); break;
        case RAIN: *dest = (void*)(Arrptr->rain); break;
        case N: *dest = (void*)(Arrptr->Manningsn); break;
        case DEM: *dest = (void*)(Arrptr->DEM); break;
        default: return 1;
    }
    return 0;
}

BMI_API int get_value(const char *name, void *dest) {
    VARIABLE_LABEL label = variable2label(name);
    int n = Parptr->xsz * Parptr->ysz;
    double *d_dest = (double*)dest;

    if (label == WATER_SURFACE_ELEVATION) {
        for (int i=0; i<n; ++i) d_dest[i] = Arrptr->H[i] + Arrptr->DEM[i];
        return 0;
    }

    void *ptr = NULL;
    if (get_value_ptr(name, &ptr) == 0) {
        memcpy(dest, ptr, n * sizeof(double));
        return 0;
    }
    return 1;
}

BMI_API int get_value_at_indices(const char *name, void *dest, int *indices, int count) {
    void *ptr = NULL;
    if (get_value_ptr(name, &ptr) != 0) return 1;
    double *d_ptr = (double*)ptr;
    double *d_dest = (double*)dest;
    for (int i=0; i<count; ++i) d_dest[i] = d_ptr[indices[i]];
    return 0;
}

BMI_API int set_value(const char *name, const void *src) {
    VARIABLE_LABEL label = variable2label(name);
    int n = Parptr->xsz * Parptr->ysz;
    void *ptr = NULL;
    if (get_value_ptr(name, &ptr) != 0) return 1;
    memcpy(ptr, src, n * sizeof(double));
    return 0;
}

BMI_API int set_value_at_indices(const char *name, int *indices, int count, const void *src) {
    void *ptr = NULL;
    if (get_value_ptr(name, &ptr) != 0) return 1;
    double *d_ptr = (double*)ptr;
    double *d_src = (double*)src;
    for (int i=0; i<count; ++i) d_ptr[indices[i]] = d_src[i];
    return 0;
}

BMI_API int get_component_name(char *name) {
    strcpy(name, "LISFLOOD-FP");
    return 0;
}

BMI_API void set_logger(Logger callback) {
    logger = callback;
    _log(INFO, "Logging attached to LISFLOOD-FP BMI");
}

} // extern "C"
