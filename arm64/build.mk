# Use source-built ARM64 graphics services; preserve all stock ARM32 libraries.
a6plte_overlay_files := $(filter-out \
    bin/hw/android.hardware.graphics.allocator@2.0-service \
    bin/hw/android.hardware.graphics.composer@2.1-service \
    etc/init/android.hardware.graphics.allocator@2.0-service.rc \
    etc/init/android.hardware.graphics.composer@2.1-service.rc, \
    $(a6plte_overlay_files))

include $(LOCAL_PATH)/arm64/modules.mk
a6plte_arm64_elf_checks := $(foreach module,$(A6PLTE_ARM64_PREBUILT_MODULES),$(call intermediates-dir-for,SHARED_LIBRARIES,$(module))/check_elf_files.timestamp)
.PHONY: a6plte-arm64-elf-checks
a6plte-arm64-elf-checks: $(a6plte_arm64_elf_checks)
# Check even when a caller builds vendor.img directly or packages a full OTA.
$(PRODUCT_OUT)/vendor.img: $(a6plte_arm64_elf_checks)
