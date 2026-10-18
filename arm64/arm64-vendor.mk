# Native ARM64 additions only; no replacement of the ARM32 Samsung stack.
include vendor/samsung/a6plte/arm64/modules.mk
PRODUCT_PACKAGES += $(A6PLTE_ARM64_PREBUILT_MODULES) liba6plte_atrace_compat
