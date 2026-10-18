# vendor/samsung/a6plte

The `vendor` partition of the Samsung Galaxy A6+ (SM-A605FN), firmware **A605FNXXU8CVA1** (Android 10), built
by the ROM build from the files in this tree. Nothing is flashed or patched on the phone afterwards.

| Path | What |
|---|---|
| `proprietary/vendor/` | the regular files of the stock `/vendor`, same relative paths (copied with `PRODUCT_COPY_FILES`) |
| `proprietary/selinux/` | the Samsung vendor SELinux policy; replaces the files `system/sepolicy` generates for the vendor |
| `links.list`, `dirs.list`, `make-links.sh` | symbolic links and empty mount-point directories (`PRODUCT_COPY_FILES` can create neither) |
| `sepolicy/` | `file_contexts` of the stock vendor (rules the build lacks) + stub `.te` types, so the build can label and check `vendor.img` |
| `aids.fs` | the 24 custom users/groups of the stock vendor (`etc/passwd`), generated; init scripts name them |
| `config.fs` | owners and file capabilities the default `fs_config` rules do not give (3 binaries) |
| `vendor.prop` | vendor properties of the stock firmware that the build does not generate (`TARGET_VENDOR_PROP`) |
| `patches/` | changes made on top of the stock files, applied by the generator (each one explains why) |
| `gen_vendor.py` | regenerates everything above from a dump of the stock `/vendor` |
| `a6plte-vendor.mk`, `Android.mk`, `BoardConfigVendor.mk` | generated / hand-written build glue |

Only blobs go in. Left out on purpose: `app/TimeService` (Samsung app), the leftovers of `app/QDMA*`, and `overlay/`
(AOSP RROs that Lineage builds and installs itself). The Trustonic trustlet in `app/mcRegistry` is a blob and stays.

Not copied because the build generates them from tracked sources: `build.prop`, `default.prop`,
`etc/vintf/manifest.xml`, `etc/vintf/compatibility_matrix.xml` (device tree), `etc/fs_config_*` (`config.fs`).

Regenerate (dump = `firmware/extracted/vendor`, made with `debugfs -R "rdump / dir"` on the stock `vendor.img`):

    python3 gen_vendor.py <stock vendor dump> .

The output repository must already exist and contain `ramdisk/init`, `ramdisk/dpolicy` and a non-empty
`lineage_vendor_installs.txt`. Optional arguments are `<build out directory|none> [stock boot ramdisk directory]`.
`none` keeps the collision snapshot; an existing build output directory without vendor install rules is rejected.
Source and output directories must not overlap. The generator validates required stock files, generates and applies
patches in a private staging directory, then publishes the generated paths. Generation failures leave the current
output untouched; publication errors roll back replaced paths. If rollback itself fails, old files are retained
in the reported staging directory. Publication spans several files and is not atomic against power loss; run it
while no build or other generator is using the output tree.

The SELinux labels of the files come from `vendor_file_contexts` at build time (as in the stock build), the
capabilities from `config.fs`. The Samsung `security.five` file-integrity xattrs cannot be reproduced.

`gen_sepolicy.py <dump> <lineage out/.../obj/ETC> .` regenerates `sepolicy/` (it asks `seinfo` which types and rules
the build already has and keeps the answer in `sepolicy/known_*.txt`).

## Why the Samsung SELinux policy remains the base

At boot `init` compiles `plat_sepolicy.cil` (system) with `vendor_sepolicy.cil` and `plat_pub_versioned.cil` (vendor).
The Samsung vendor domains (`tee`, `hal_*_qti`, `vendor_per_mgr`, ...) only exist in the stock vendor policy, so those
files must be the stock ones; the stub types in `sepolicy/` would make every Samsung service run unconfined or fail.
`Android.mk` installs the stock files with `LOCAL_OVERRIDES_PACKAGES` in place of the ones `system/sepolicy` builds.

There is no `precompiled_sepolicy` in the vendor: `PRODUCT_PRECOMPILED_SEPOLICY := false` keeps the build from making one
(with the stub types, and with a sha256 that would match the Lineage system, `init` would load it instead of compiling).
`init` then compiles `plat_sepolicy.cil` + the Samsung `vendor_sepolicy.cil` at boot (a few seconds), as it did with
the stock vendor under Lineage's system. The stock `precompiled_sepolicy*` are not copied: system/sepolicy installs them
at the same path when there is no odm image.

## Device policy additions and Trustonic nodes (2026-10-18)

`policy/` contains reviewed additions to the stock runtime CIL, file, hwservice and property contexts.
`gen_vendor.py` appends these once to freshly copied stock files in staging. Run `gen_sepolicy.py` with
`none` before regenerating vendor when changing vendor file labels; it also reads `policy/vendor_file_contexts`.
The build declarations in `sepolicy/capabilityconfigstore.te` and context files match the runtime additions.

Qualcomm capabilityconfigstore has its own executable domain and HIDL service label. Its configuration under
`/vendor/etc/configstore` is read-only; framework/media clients can query it, untrusted apps cannot register it.
Do not replace this with generic init execution permissions on `vendor_file` or a permissive domain.
Validate the final Samsung-plus-platform policy with Android's secilc options, including the same `-N` used
by init. Checking neverallows separately must be compared against the unmodified stock baseline; Samsung
and PE already have incompatible neverallows unrelated to these additions.

`patches/0002-*` assigns Trustonic device ownership through ueventd, including `/dev/mobicore-user` created
by the daemon after boot. The matching loader/daemon init and fingerprint feature are in msm8953-common;
the existing Samsung fingerprint HAL already exports the standard 2.1 interface. NFC framework/Tag are
also selected there. Enrollment, NFC transactions and Trustonic startup still require a full-ROM boot test.

The boot ramdisk path follows `PRODUCT_OUT`, including custom `OUT_DIR` builds.
