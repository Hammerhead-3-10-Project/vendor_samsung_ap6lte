# Validate the policy actually installed by the Samsung vendor overlay, rather
# than just the build-time type stubs. Keep flags aligned with Android 10 init.
a6plte_runtime_policy := $(PRODUCT_OUT)/obj/PACKAGING/a6plte_runtime_policy_intermediates/policy
a6plte_runtime_plat := $(call intermediates-dir-for,ETC,plat_sepolicy.cil)/plat_sepolicy.cil
a6plte_runtime_mapping := $(call intermediates-dir-for,ETC,plat_mapping_file)/30.0.cil
# The stock vendor is Android 10 (29.0): PE 11 maps it through the 29.0 compat file.
a6plte_runtime_compat := $(call intermediates-dir-for,ETC,29.0.compat.cil)/29.0.compat.cil
a6plte_runtime_vendor := $(LOCAL_PATH)/proprietary/selinux
$(a6plte_runtime_policy): PRIVATE_PLAT := $(a6plte_runtime_plat)
$(a6plte_runtime_policy): PRIVATE_MAPPING := $(a6plte_runtime_mapping)
$(a6plte_runtime_policy): PRIVATE_COMPAT := $(a6plte_runtime_compat)
$(a6plte_runtime_policy): PRIVATE_VENDOR := $(a6plte_runtime_vendor)
$(a6plte_runtime_policy): PRIVATE_ADDITIONS := $(LOCAL_PATH)/policy
$(a6plte_runtime_policy): $(a6plte_runtime_plat) $(a6plte_runtime_mapping) $(a6plte_runtime_compat) \
        $(a6plte_runtime_vendor)/plat_pub_versioned.cil \
        $(a6plte_runtime_vendor)/vendor_sepolicy.cil \
        $(a6plte_runtime_vendor)/vendor_file_contexts \
        $(LOCAL_PATH)/policy/vendor_hwservice_contexts \
        $(LOCAL_PATH)/policy/vendor_property_contexts \
        $(HOST_OUT_EXECUTABLES)/secilc $(HOST_OUT_EXECUTABLES)/checkfc
	@echo "Validate the Samsung vendor runtime policy: $@"
	$(hide) mkdir -p $(dir $@)
	$(hide) $(HOST_OUT_EXECUTABLES)/secilc -m -M true -G -N -c 30 \
	    $(PRIVATE_PLAT) $(PRIVATE_MAPPING) \
	    $(PRIVATE_VENDOR)/plat_pub_versioned.cil $(PRIVATE_VENDOR)/vendor_sepolicy.cil $(PRIVATE_COMPAT) \
	    -o $@.tmp -f /dev/null
	# /system/etc/install-recovery.sh belongs to the system partition and its type is gone in Android 11.
	$(hide) grep -v 'install_recovery_exec' $(PRIVATE_VENDOR)/vendor_file_contexts > $@.fc
	$(hide) $(HOST_OUT_EXECUTABLES)/checkfc $@.tmp $@.fc && rm -f $@.fc
	$(hide) $(HOST_OUT_EXECUTABLES)/checkfc -l $@.tmp $(PRIVATE_ADDITIONS)/vendor_hwservice_contexts
	$(hide) $(HOST_OUT_EXECUTABLES)/checkfc -p $@.tmp $(PRIVATE_ADDITIONS)/vendor_property_contexts
	$(hide) mv $@.tmp $@

.PHONY: a6plte-runtime-policy
a6plte-runtime-policy: $(a6plte_runtime_policy)
