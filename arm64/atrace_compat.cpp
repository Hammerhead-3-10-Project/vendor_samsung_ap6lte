// Android 11 Adreno clients call a function that Android 10 exposes inline.
// Reuse Android 10 initialization and enabled-tag semantics without disabling tracing.
#define atrace_get_enabled_tags a6plte_inline_atrace_get_enabled_tags
#include <cutils/trace.h>
#undef atrace_get_enabled_tags

extern "C" uint64_t atrace_get_enabled_tags() {
    return a6plte_inline_atrace_get_enabled_tags();
}
