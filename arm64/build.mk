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
