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

The SELinux labels of the files come from `vendor_file_contexts` at build time (as in the stock build), the
capabilities from `config.fs`. The Samsung `security.five` file-integrity xattrs cannot be reproduced.

`gen_sepolicy.py <dump> <lineage out/.../obj/ETC> .` regenerates `sepolicy/` (it asks `seinfo` which types and rules
the build already has and keeps the answer in `sepolicy/known_*.txt`).

## Why the stock SELinux policy is shipped as is

At boot `init` compiles `plat_sepolicy.cil` (system) with `vendor_sepolicy.cil` and `plat_pub_versioned.cil` (vendor).
The Samsung vendor domains (`tee`, `hal_*_qti`, `vendor_per_mgr`, ...) only exist in the stock vendor policy, so those
files must be the stock ones; the stub types in `sepolicy/` would make every Samsung service run unconfined or fail.
`Android.mk` installs the stock files with `LOCAL_OVERRIDES_PACKAGES` in place of the ones `system/sepolicy` builds.

The stock `precompiled_sepolicy*` files are copied unchanged. Their stored sha256 is that of the Samsung system policy;
it never matches Lineage's `plat_sepolicy.cil`, so `init` ignores the precompiled policy and compiles plat + vendor at
boot (a few seconds), exactly as it did on the stock vendor with Lineage's system. `PRODUCT_PRECOMPILED_SEPOLICY := false`
only keeps the build from generating a precompiled policy of its own (built with the stub types, it would match).
