// Android 11 Adreno clients import atrace_get_enabled_tags(), which the Android 10 VNDK libcutils
// (the one the vendor namespace loads) only provides inline. Same semantics as the Android 10
// implementation: the tags come from debug.atrace.tags.enableflags, 0 when unset.
#include <stdint.h>
#include <stdlib.h>
#include <cutils/properties.h>

extern "C" uint64_t atrace_get_enabled_tags() {
    char value[PROPERTY_VALUE_MAX];
    if (property_get("debug.atrace.tags.enableflags", value, "0") <= 0) return 0;
    return strtoull(value, nullptr, 0);
}
