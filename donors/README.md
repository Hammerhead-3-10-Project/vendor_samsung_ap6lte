# ARM64 donor candidates

These manifests pin investigation inputs. They are not referenced by the Android build and do not
replace the stock `proprietary/` files. Android 11 origin does not automatically disqualify a blob from
an Android 10 port; actual ELF imports, linker visibility and hardware/kernel contracts decide.

## A20s GPU candidate, inspected 2026-10-18

Source: [GalaxyA20s/vendor_samsung_a20s](https://github.com/GalaxyA20s/vendor_samsung_a20s/tree/c708f666ab857d8c6ba1f1673715defa3a5fb3e8),
firmware A207MUBS4CWF1, Android 11/API30. `a20s-gpu.json` selects 26 files (98,271,156 bytes) in both
ARM32 and ARM64 variants: EGL/GLES, Vulkan, GSL, Adreno utilities, OpenCL/CB and their LLVM compilers.
It also records exact sizes, Git blob IDs and SHA256, preventing a later upstream change from silently
changing the candidate. This is a candidate inventory, not a complete or validated graphics vendor.

From the vendor repository, fetch into a separate host scratch directory:

```sh
python3 donors/fetch.py donors/a20s-gpu.json /path/outside/vendor/a20s-candidate
```

The fetcher validates size, Git blob ID, SHA256 and ELF class/machine. Existing files are reused only
if they match; mismatches stop without overwriting them. It refuses destinations inside this vendor
repository. No installation, build configuration, phone access or ELF modification is performed.

### Static findings

- Of 2,651 explicit versioned libc/libdl/libm/liblog imports checked across 49 downloaded A20s ELF
  files, 1,730 belong to this GPU selection. All 1,730 GPU imports occur in the matching ARM32/ARM64
  export maps of our Android 10 checkout. This is a limited source-map check, not a complete linker test:
  unversioned C++/HIDL/platform symbols, namespaces and dynamically loaded libraries remain unverified.
- `libCB.so` contains references to `libllvm-qcom.so` in addition to DT_NEEDED. Both LLVM compilers
  are included. Strings also mention `libkernelmanager.so` and application-profile/other-platform
  libraries; strings alone do not establish which paths execute on this device.
- The A20s kernel reference
  [e8bedc92132230962d4bbaca3af56fdaf67a2a80](https://github.com/GalaxyA20s/android_kernel_samsung_a20s/tree/e8bedc92132230962d4bbaca3af56fdaf67a2a80)
  has an `include/uapi/linux/msm_kgsl.h` identical to the local A6+ 4.9 header. The reference kernel is
  4.9.227; correspondence to the exact donor firmware is unproven. Matching headers support further
  evaluation but do not establish identical ioctl implementations, firmware or runtime behavior.
- Retained A6+ ARM32 GLES/Vulkan import `gsl_shared_memory_import`, absent from donor GSL exports.
  A GSL-only substitution therefore removes a named dependency of those clients. Evaluate the matching
  GPU set together; do not assume the presence of a library with the same filename means ABI compatibility.
- An ARM64 system still needs mapper/gralloc and a RenderScript implementation or tested fallback.
  These are not solved by the GPU inventory. No ARM64 `libRSDriver_adreno.so` was found in the donor tree.

### Other A20s groups inspected, not selected for installation

| Group | Finding | Next check |
|---|---|---|
| Mapper/gralloc | Donor mapper advertises 2.0, A6+ stock manifest declares 2.1; native handles/metadata must agree with both client ABIs and retained HALs. | Select a coherent mapper/allocator/composer/metadata implementation and correct VINTF. |
| Metadata/SDM/HWC | Metadata requires libgralloc.qti.so and libgralloctypes.so; HWC needs more display libraries. SDM imports `_Unwind_Resume@LIBC_R`, not in the Android 10 libc export map. | Build the full link closure. The LIBC_R mismatch alone is not proof of load failure: Android's linker can use unversioned global exports from another dependency; exact ARM64 outputs are needed. |
| OMX | Initial versioned platform-import checks pass, but decoder/encoder require libhypv_intercept, color conversion/black-bar libraries and metadata dependencies. | Check complete dependency/symbol closure and VIDC ioctls against the actual kernel/firmware. |
| Perf | Uses perf 2.0 and several additional configuration/client/glue libraries. | Check A6+ service interfaces, properties and sysfs paths; do not transplant a standalone perfd library. |
| Thermal | The executable is AArch64; sensor names, limits and cooling paths are device specific. | Preserve A6+ thermal control during the architecture migration. |

The stock OpenCL comparison also finds removed ARM helper exports named by libsnap_compute.so; these
helpers may be supplied elsewhere, so this is a resolution check to perform, not proof that the client
must fail. Struct layouts and opaque handles are not checked by comparing exported symbol names.

Detailed host evidence and reproducer scripts are in the project directory at
`reports/arm64-migration-20261018/`. No candidate has been flashed, run or benchmarked on A6+.
