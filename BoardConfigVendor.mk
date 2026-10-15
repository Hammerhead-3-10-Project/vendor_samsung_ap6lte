# Samsung Galaxy A6+ (SM-A605FN) vendor partition built from the files of this tree.
# Included by device/samsung/a6plte/BoardConfig.mk.

# vendor/build.prop: properties of the stock vendor that the build does not generate (vendor.prop)
TARGET_VENDOR_PROP += vendor/samsung/a6plte/vendor.prop

# owners and file capabilities (config.fs)
TARGET_FS_CONFIG_GEN += vendor/samsung/a6plte/config.fs

# file_contexts of the stock vendor + stubs for its types: needed to label and check vendor.img at build time.
# (The policy that runs on the phone is the Samsung one in proprietary/selinux, see Android.mk.)
BOARD_SEPOLICY_DIRS += vendor/samsung/a6plte/sepolicy
