#include <stddef.h>

static int count(const char *p, size_t n) {
    int k = 0;
    if (p == NULL) {
        return -1;
    } else if (n > 0 && p[0] == 'a') {
        k = 1;
    }
    for (size_t i = 0; i < n; ++i) {
        while (p[i] == ' ') { ++i; }
    }
    return k;
}
