# Use source-built ARM64 graphics/configstore services; preserve stock ARM32 libraries.
# The generated configstore seccomp policy uses TARGET_ARCH. Overlaying Samsung's
# ARM32 executable would terminate it on fstat64 and block SurfaceFlinger startup.
a6plte_overlay_files := $(filter-out \
    bin/hw/android.hardware.configstore@1.1-service \
    bin/hw/android.hardware.graphics.allocator@2.0-service \
    bin/hw/android.hardware.graphics.composer@2.1-service \
    etc/init/android.hardware.graphics.allocator@2.0-service.rc \
    etc/init/android.hardware.graphics.composer@2.1-service.rc \
    etc/init/android.hardware.configstore@1.1-service.rc, \
    $(a6plte_overlay_files))

include $(LOCAL_PATH)/arm64/modules.mk
a6plte_arm64_blob_inputs := $(shell python3 $(LOCAL_PATH)/arm64/verify-blobs.py --inputs)
a6plte_arm64_integrity := $(PRODUCT_OUT)/obj/PACKAGING/a6plte_arm64_blob_integrity_intermediates/verified.stamp
$(a6plte_arm64_integrity): PRIVATE_CHECKER := $(LOCAL_PATH)/arm64/verify-blobs.py
$(a6plte_arm64_integrity): $(LOCAL_PATH)/arm64/verify-blobs.py $(LOCAL_PATH)/arm64/selected-blobs.json $(LOCAL_PATH)/arm64/blob-fixups.json $(addprefix $(LOCAL_PATH)/arm64/blobs/,$(a6plte_arm64_blob_inputs))
	@echo "Verify pinned ARM64 blob integrity: $@"
	$(hide) rm -f $@
	$(hide) mkdir -p $(dir $@)
	$(hide) python3 $(PRIVATE_CHECKER)
	$(hide) touch $@

a6plte_arm64_elf_checks := $(foreach module,$(A6PLTE_ARM64_PREBUILT_MODULES),$(call intermediates-dir-for,SHARED_LIBRARIES,$(module))/check_elf_files.timestamp) $(a6plte_arm64_integrity)
.PHONY: a6plte-arm64-elf-checks
a6plte-arm64-elf-checks: $(a6plte_arm64_elf_checks)
# Check even when a caller builds vendor.img directly or packages a full OTA.
$(PRODUCT_OUT)/vendor.img: $(a6plte_arm64_elf_checks)

# Donor display composer. Its dependencies (libdrmutils, libgpu_tonemapper, ...) are Make
# modules that Soong cannot see, so these are declared here as ELF-checked Make prebuilts.
define a6plte-arm64-donor-lib
include $$(CLEAR_VARS)
LOCAL_MODULE := $(1)
LOCAL_MODULE_STEM := $(2)
LOCAL_SRC_FILES := arm64/blobs/lib64/$(3)$(2).so
LOCAL_MODULE_CLASS := SHARED_LIBRARIES
LOCAL_MODULE_SUFFIX := .so
LOCAL_MODULE_RELATIVE_PATH := $(3)
LOCAL_MULTILIB := 64
LOCAL_VENDOR_MODULE := true
LOCAL_MODULE_TAGS := optional
LOCAL_STRIP_MODULE := false
LOCAL_CHECK_ELF_FILES := true
LOCAL_SHARED_LIBRARIES := $(4)
include $$(BUILD_PREBUILT)
endef
$(eval $(call a6plte-arm64-donor-lib,a6plte_arm64_libsdmutils,libsdmutils_a11,,libc++))
$(eval $(call a6plte-arm64-donor-lib,a6plte_arm64_libsdmcore,libsdmcore_a11,,a6plte_arm64_libsdmutils libdrm libdrmutils libc++))
$(eval $(call a6plte-arm64-donor-lib,a6plte_arm64_hwcomposer.msm8953,hwcomposer.a11,hw/,a6plte_arm64_libsdmcore a6plte_arm64_libsdmutils a6plte_arm64_libqdMetaData a6plte_arm64_libgrallocutils libqservice libbinder libhardware libhardware_legacy libutils libcutils libsync libqdutils libdrmutils libc++ liblog vendor.display.config@2.0 libhidlbase libhidltransport a6plte_arm64_libdisplayconfig.qti libui libgpu_tonemapper))
