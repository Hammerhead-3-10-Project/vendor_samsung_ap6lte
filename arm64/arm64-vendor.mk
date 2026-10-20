# Native ARM64 additions only; no replacement of the ARM32 Samsung stack.
include vendor/samsung/a6plte/arm64/modules.mk
PRODUCT_PACKAGES += $(A6PLTE_ARM64_PREBUILT_MODULES)

# Android 10 keymaster libraries for the stock Samsung keymaster 3.0 HAL (see a10-compat/README.md).
PRODUCT_COPY_FILES += $(foreach l,libkeymaster_portable libkeymaster_messages libpuresoftkeymasterdevice libsoftkeymasterdevice,\
    vendor/samsung/a6plte/a10-compat/lib/$(l).so:$(TARGET_COPY_OUT_VENDOR)/lib/$(l).so)
