# Native ARM64 additions only; no replacement of the ARM32 Samsung stack.
include vendor/samsung/a6plte/arm64/modules.mk
PRODUCT_PACKAGES += $(A6PLTE_ARM64_PREBUILT_MODULES)

# The Android 10 keymaster libraries (a10-compat/lib) are copied by the overlay step in Android.mk,
# after every module install: Soong modules would otherwise collide on the same /vendor/lib paths.
