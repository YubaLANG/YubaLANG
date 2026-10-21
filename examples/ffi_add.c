#include <stdint.h>

#ifdef _WIN32
__declspec(dllexport)
#else
__attribute__((visibility("default")))
#endif
int32_t yubalang_add_i32(int32_t left, int32_t right) {
    return left + right;
}
