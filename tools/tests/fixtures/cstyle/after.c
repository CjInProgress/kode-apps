#include <stddef.h>

static int count(const char *p, size_t n) {
    int k = 0;
    if ( NULL == p )
    {
        return -1;
    }
    else if ( 0 < n && 'a' == p[0] )
    {
        k = 1;
    }
    for ( size_t i = 0; i < n; ++i )
    {
        while ( ' ' == p[i] ) { ++i; }
    }
    return k;
}
