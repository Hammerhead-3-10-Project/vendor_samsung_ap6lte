# Samsung Galaxy A6+ (SM-A605FN) vendor partition built from the files of this tree.
# Included by device/samsung/a6plte/BoardConfig.mk.

# vendor/build.prop: properties of the stock vendor that the build does not generate (vendor.prop)
TARGET_VENDOR_PROP += vendor/samsung/a6plte/vendor.prop

# owners and file capabilities (config.fs)
TARGET_FS_CONFIG_GEN += vendor/samsung/a6plte/config.fs

# file_contexts of the stock vendor + stubs for its types: needed to label and check vendor.img at build time.
# (The policy that runs on the phone is the Samsung one in proprietary/selinux, see Android.mk.)
BOARD_SEPOLICY_DIRS += vendor/samsung/a6plte/sepolicy

# custom users/groups of the stock vendor (vendor_qrtr, vendor_thermal, ...), generated from its etc/passwd
TARGET_FS_CONFIG_GEN += vendor/samsung/a6plte/aids.fs

# vendor/build.prop ro.vendor.build.security_patch (the Samsung keymaster reads the vendor patch level)
VENDOR_SECURITY_PATCH := 2021-12-01

# The boot image needs a ramdisk with the first-stage init (see Android.mk, a6plte_ramdisk). BOARD_BUILD_SYSTEM_ROOT_IMAGE makes
# the build leave it out, so it is passed by hand; the path is the one of the rule in Android.mk.
BOARD_MKBOOTIMG_ARGS += --ramdisk out/target/product/$(TARGET_DEVICE)/obj/PACKAGING/a6plte_ramdisk_intermediates/ramdisk.img
