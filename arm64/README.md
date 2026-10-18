# Native ARM64 additions

This layer supplements the ARM32 A6+ vendor without replacing its GPU, camera, RIL, TEE or media codecs.
The matching product uses source-built ARM64 graphics services and Android 10 media wrappers/helpers.

`selected-blobs.json` pins the fifteen upstream A20s files at commit
`c708f666ab857d8c6ba1f1673715defa3a5fb3e8`, including original Git blob IDs and SHA256.
`Android.bp` declares their real SONAMEs, dependencies and enabled ELF checks. `modules.mk` is the single
selection list used by the product and `build.mk` image validation. `build.mk` also removes only the old
allocator/composer executables/init definitions from the final stock overlay.

The Android 11 GLESv2/Vulkan/CB/C2D2 blobs import `atrace_get_enabled_tags`, which Android 10 implements
as a header inline. `atrace_compat.cpp` exports the same behavior using that inline; it does not return
fake tags or disable tracing. These four blobs add a DT_NEEDED on `liba6plte_atrace_compat.so`.
`blob-fixups.json` records original/patched hashes. Their instruction sections are unchanged.
The bridge has the existing `same_process_hal_file` label; no permissive policy is added.

Refresh from the pinned donor in an external scratch directory, while builds are idle:

```sh
python3 donors/fetch.py arm64/selected-blobs.json /path/outside/vendor/a20s-cache
python3 arm64/refresh-blobs.py /path/outside/vendor/a20s-cache --patchelf /path/to/patchelf
```

The reviewed fixups use patchelf 0.18.0. The project extracted Ubuntu's 0.18.0-1.4build1 package under
`/run/media/fenixdev/sorgenti/arm64-port/host-tools/patchelf`; no system installation is needed.
The refresh script validates all inputs and patched hashes plus executable sections before publication.
Per-file publication is atomic, but publication of the whole set is not atomic against interruption.
A different tool layout/hash requires review rather than silently accepting new bytes.

`gen_vendor.py` deliberately leaves `arm64/` outside its generated output paths. It excludes stock
zygote/Bionic/ISA properties and keeps the ELF guard in the stock overlay recipe. Regeneration therefore
preserves the native files and the matching Android 10 architecture properties.

The real Android ELF checks and Samsung runtime-policy validation pass in the isolated ARM64 build.
The fifteen checked files are required before the vendor overlay/image is made. No allow-undefined-symbol
exception or disabled ELF check is used. Full OTA packaging, buffer/metadata interoperability and hardware
runtime behavior remain untested; these source/build results do not certify a successful device boot.

`verify-blobs.py` also enforces the pinned/fixed hashes and AArch64 ELF headers during the build.
This is required alongside the ELF checks: Android's generic checker can skip non-ELF inputs.
A source file accidentally replacing a blob must fail the image build, not be skipped as non-ELF.
