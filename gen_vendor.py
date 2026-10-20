#!/usr/bin/env python3
"""Generate the vendor tree of the Galaxy A6+ (SM-A605FN) from a dump of the stock /vendor partition.

    python3 gen_vendor.py <stock vendor dump> <output repo dir>

The dump is the content of the vendor partition of the firmware A605FNXXU8CVA1 (debugfs rdump / mounted image).
Output (everything is regenerated, nothing is edited by hand):
  proprietary/vendor/...      regular files, same relative path as in /vendor
  proprietary/selinux/...     the Samsung vendor SELinux policy files (they replace the ones the build generates)
  links.list, dirs.list       symbolic links (path<TAB>target) and empty directories of the stock vendor
  a6plte-vendor.mk            PRODUCT_COPY_FILES + PRODUCT_PACKAGES
  vendor.prop                 vendor properties that the build does not generate itself
"""
import argparse
from contextlib import contextmanager
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def walk_error(error):
    raise error


def generate(src, dst, LINEAGE_OUT, RAMDISK_SRC):
    # A build out directory refreshes lineage_vendor_installs.txt; None keeps the validated snapshot.
    # An empty snapshot would reintroduce collisions with ROM build modules.
    if RAMDISK_SRC:
        os.makedirs(os.path.join(dst, 'ramdisk'), exist_ok=True)
        for fn, mode in (('init', 0o750), ('dpolicy', 0o644)):
            shutil.copyfile(os.path.join(RAMDISK_SRC, fn), os.path.join(dst, 'ramdisk', fn))
            os.chmod(os.path.join(dst, 'ramdisk', fn), mode)
    INSTALLS = os.path.join(dst, 'lineage_vendor_installs.txt')
    if LINEAGE_OUT:
        # Every file the Lineage build has a rule for under /vendor (Soong and Android.mk modules), from the ninja files.
        import glob, re
        pat = re.compile(r'out[^/\s]*/target/product/[^/\s:$|]+/vendor/[^\s:$|]+')
        found = set()
        for f in glob.glob(LINEAGE_OUT + '/*.ninja') + [LINEAGE_OUT + '/soong/build.ninja']:
            if not os.path.isfile(f):
                continue
            with open(f, errors='ignore') as ninja:
                for line in ninja:
                    if line.startswith('build ') and '/vendor/' in line:
                        for m in pat.findall(line.split(':')[0]):
                            found.add(m.split('/vendor/', 1)[1])
        if not found:
            raise ValueError('No vendor install rules found in the supplied out directory')
        Path(INSTALLS).write_text('\n'.join(sorted(found)) + '\n')
    lineage_installs = set(Path(INSTALLS).read_text().split()) if os.path.exists(INSTALLS) else set()
    PATH = 'vendor/samsung/a6plte'

    # Files the build generates itself from tracked sources (manifest/matrix from the device tree, fs_config from
    # config.fs, build.prop/default.prop from the board config + vendor.prop) or that are only placeholders.
    GENERATED = {'build.prop', 'default.prop', 'etc/vintf/manifest.xml', 'etc/vintf/compatibility_matrix.xml',
                 'etc/fs_config_dirs', 'etc/fs_config_files',
                 # system/sepolicy installs these in /odm if there is an odm image and in /vendor otherwise (there is none
                 # here), so a copy would be a second rule for the same path. They are not wanted anyway: their stored
                 # sha256 is the Samsung system's, init ignores them and compiles the policy at boot.
                 'etc/selinux/precompiled_sepolicy', 'etc/selinux/precompiled_sepolicy.plat_sepolicy_and_mapping.sha256',
                 'etc/selinux/precompiled_sepolicy.product_sepolicy_and_mapping.sha256'}
    # Only blobs go in: no apps and no overlays. overlay/ holds AOSP RROs that Lineage builds and installs itself;
    # app/ holds TimeService.apk and the leftovers of QDMA (the Trustonic trustlet in app/mcRegistry is a blob and stays).
    SKIP_DIRS = ('lost+found', 'odm', 'overlay', 'app/TimeService', 'app/QDMA', 'app/QDMA-UI')
    SELINUX_DIR = 'etc/selinux'
    SELINUX_TOP = {'plat_pub_versioned.cil', 'plat_sepolicy_vers.txt', 'vendor_file_contexts', 'vendor_hwservice_contexts',
                   'vendor_mac_permissions.xml', 'vendor_property_contexts', 'vendor_seapp_contexts',
                   'vendor_sepolicy.cil', 'vndservice_contexts'}

    # AOSP userland that the Lineage build compiles from source and installs in /vendor (shell_and_utilities_vendor, ...):
    # the stock copies are not used, Lineage's are.
    LINEAGE_WINS = {'bin/awk', 'bin/grep', 'bin/sh', 'bin/toolbox', 'bin/toybox_vendor', 'bin/logwrapper', 'bin/dumpsys',
                    'bin/cplay', 'bin/vndservice', 'bin/vndservicemanager', 'etc/init/vndservicemanager.rc', 'etc/mkshrc',
                    'etc/passwd', 'etc/group', 'etc/NOTICE.xml.gz', 'etc/permissions/handheld_core_hardware.xml'}
    # init scripts the Lineage build installs that define a service the stock vendor already defines (same name, other
    # arguments/groups). init reads /vendor/etc/init in alphabetical order and ignores the later duplicate, which would
    # make Lineage's (weaker) definition win for vendor.media.omx. They are removed by the copy step.
    LINEAGE_REMOVE = ['etc/init/rild.legacy.rc', 'etc/init/android.hardware.media.omx@1.0-service.rc',
                      'etc/vintf/manifest/android.hardware.cas@1.1-service.xml', 'etc/init/android.hardware.cas@1.1-service.rc', 'bin/hw/android.hardware.cas@1.1-service']   # PE11 builds its own cas@1.2 service: the stock 1.1 one would conflict in the VINTF manifest
    LINK_TARGETS_LINEAGE = {'toybox_vendor', 'toolbox', 'grep'}   # the toybox applet links are created by the toybox_vendor module

    # properties the build writes into vendor/build.prop itself
    GEN_PROP_PREFIX = ('ro.vendor.build.date', 'ro.vendor.build.fingerprint', 'ro.vendor.build.id', 'ro.vendor.build.tags',
                       'ro.vendor.build.type', 'ro.vendor.build.version.incremental', 'ro.vendor.build.version.release',
                       'ro.vendor.build.version.sdk', 'ro.vendor.build.security_patch',   # VENDOR_SECURITY_PATCH
                       'ro.product.vendor.', 'ro.vendor.product.cpu.', 'ro.bootimage.build.',
                       'ro.product.first_api_level', 'ro.product.board', 'ro.board.platform',
                       'ro.bionic.', 'dalvik.vm.isa.',
                       'ro.vndk.lite',
                       # the build writes ro.vndk.version (BOARD_VNDK_VERSION=current -> 30): the stock 29 would make the
                       # vendor look for the v29 APEX while the vendor modules built from source link against the 30 VNDK
                       'ro.vndk.version')
    # NOT generated and kept: ro.vendor.build.version.sehi (Samsung)

    copies, overlay, skipped_aosp, selinux, links, dirs = [], [], [], [], [], []
    for root, dnames, fnames in os.walk(src, onerror=walk_error):
        rel = os.path.relpath(root, src)
        rel = '' if rel == '.' else rel
        dnames[:] = sorted(d for d in dnames if os.path.join(rel, d) not in SKIP_DIRS)
        if not dnames and not fnames and rel:
            dirs.append(rel)
        for name in sorted(fnames + [d for d in dnames if os.path.islink(os.path.join(root, d))]):
            p = os.path.join(root, name)
            r = os.path.join(rel, name)
            if os.path.islink(p):
                links.append((r, os.readlink(p)))
            elif os.path.isfile(p):
                if r in GENERATED:
                    continue
                assert not r.endswith('.apk'), 'apk in the vendor tree: ' + r
                if rel == SELINUX_DIR and name in SELINUX_TOP:
                    selinux.append(r)
                    out = os.path.join(dst, 'proprietary', 'selinux', name)
                elif r in LINEAGE_WINS:
                    skipped_aosp.append(r)
                    continue
                else:
                    (overlay if r in lineage_installs else copies).append(r)
                    out = os.path.join(dst, 'proprietary', 'vendor', r)
                os.makedirs(os.path.dirname(out), exist_ok=True)
                shutil.copyfile(p, out)
                os.chmod(out, 0o755 if r.startswith('bin/') else 0o644)
    # symlinks that os.walk lists under dnames (links to directories)
    for root, dnames, fnames in os.walk(src, onerror=walk_error):
        for d in dnames:
            p = os.path.join(root, d)
            if os.path.islink(p):
                r = os.path.relpath(p, src)
                if any(r == k or r.startswith(k + '/') for k in SKIP_DIRS):
                    continue
                if (r, os.readlink(p)) not in links:
                    links.append((r, os.readlink(p)))
    # changes made on top of the stock files (patches/*.patch, unified diffs relative to proprietary/vendor)
    import glob, subprocess
    for pf in sorted(glob.glob(os.path.join(dst, 'patches', '*.patch'))):
        subprocess.run(['patch', '-p1', '--no-backup-if-mismatch', '-d', os.path.join(dst, 'proprietary', 'vendor'),
                        '-i', pf], check=True, stdout=subprocess.DEVNULL)
        print('applied', os.path.basename(pf))
    # Runtime policy is stock Samsung plus reviewed device-specific additions.
    # Keep additions separate from blobs so regeneration cannot silently drop fixes.
    for name in ('vendor_sepolicy.cil', 'vendor_file_contexts',
                 'vendor_hwservice_contexts', 'vendor_property_contexts'):
        addition = Path(dst) / 'policy' / name
        if addition.is_file():
            with (Path(dst) / 'proprietary/selinux' / name).open('a') as output:
                output.write('\n' + addition.read_text())
    # PRODUCT_COPY_FILES runs xmllint on every .xml it copies and stops the build if it fails. Some Qualcomm files are not
    # well-formed (a comment before the XML declaration). They are blobs and stay untouched: the copy step installs them.
    import shutil as _sh
    bad_xml = []
    if _sh.which('xmllint'):
        for c in list(copies):
            if c.endswith('.xml') and subprocess.run(['xmllint', '--noout', os.path.join(dst, 'proprietary', 'vendor', c)],
                                                     capture_output=True).returncode:
                copies.remove(c); overlay.append(c); bad_xml.append(c)
    else:
        print('WARNING: xmllint not found, the .xml files were not checked')
    # Android 11 rejects VINTF metadata in PRODUCT_COPY_FILES (build/make/core/Makefile): the stock manifest fragments
    # are installed by the overlay step instead.
    for c in list(copies):
        if c.startswith('etc/vintf/'):
            copies.remove(c); overlay.append(c)
    # PE 11's host_init_verifier rejects init scripts that name HIDL interfaces the tree does not define (vendor.samsung.*,
    # wigig netperftuner) or use the removed load_system_props. They are stock files and stay untouched: the overlay step
    # installs them, so the verification is skipped for them only.
    import re as _re
    rc_unknown = _re.compile(r'^\s*(interface\s+vendor\.(samsung|qti\.hardware\.wigig)|load_system_props)', _re.M)
    for c in list(copies):
        if c.startswith('etc/init/') and c.endswith('.rc') and rc_unknown.search(
                Path(dst, 'proprietary', 'vendor', c).read_text(errors='replace')):
            copies.remove(c); overlay.append(c)
    before = len(links)
    links = [(p, t) for p, t in links if not (os.path.basename(t) in LINK_TARGETS_LINEAGE)]
    dropped_links = before - len(links)
    # Android 10 vendor services ask for libprotobuf-cpp-lite.so; the Android 11 vendor variant is installed with the
    # versioned name only (same library, protobuf 3.9.1), so alias it.
    for lib in ('lib', 'lib64'):
        l = (lib + '/libprotobuf-cpp-lite.so', 'libprotobuf-cpp-lite-3.9.1.so')
        if l not in links:
            links.append(l)
    links.sort(); dirs.sort(); copies.sort(); overlay.sort()

    with open(os.path.join(dst, 'links.list'), 'w') as f:
        f.writelines('%s\t%s\n' % l for l in links)
    with open(os.path.join(dst, 'overlay.list'), 'w') as f:
        f.writelines(o + '\n' for o in overlay)
    with open(os.path.join(dst, 'dirs.list'), 'w') as f:
        f.writelines(d + '\n' for d in dirs)

    with open(os.path.join(dst, 'a6plte-vendor.mk'), 'w') as f:
        f.write('# Generated by gen_vendor.py from the stock vendor partition. Do not edit.\n\n')
        f.write('A6PLTE_VENDOR_PATH := %s\n\n' % PATH)
        f.write('PRODUCT_COPY_FILES += \\\n')
        f.write(' \\\n'.join('    $(A6PLTE_VENDOR_PATH)/proprietary/vendor/%s:$(TARGET_COPY_OUT_VENDOR)/%s' % (c, c) for c in copies))
        f.write('\n\n# symbolic links and empty directories (module in Android.mk); the Samsung SELinux policy is copied over the\n')
        f.write('# generated one by a build step in Android.mk\n')
        f.write('PRODUCT_PACKAGES += a6plte_vendor_links\n')
        f.write('# No precompiled_sepolicy: one made by the build would use the stub types of sepolicy/ (and its sha256 would match the\n')
        f.write('# Lineage system), so init could load it instead of compiling plat + the Samsung vendor policy at boot.\n')
        f.write('PRODUCT_PRECOMPILED_SEPOLICY := false\n')

    # custom users/groups of the stock vendor (etc/passwd, uid in the OEM ranges): the build only accepts them in init
    # scripts (host_init_verifier) if they are declared as AIDs. aids.fs is added to TARGET_FS_CONFIG_GEN.
    aids = []
    for l in Path(src, 'etc/passwd').read_text().splitlines():
        f = l.strip().split(':')
        if len(f) > 3 and (2900 <= int(f[2]) <= 2999 or 5000 <= int(f[2]) <= 5999):
            aids.append((f[0], int(f[2])))
    with open(os.path.join(dst, 'aids.fs'), 'w') as f:
        f.write('# Custom users and groups of the stock vendor (its etc/passwd). Generated by gen_vendor.py. Do not edit.\n')
        for name, uid in sorted(aids, key=lambda a: a[1]):
            f.write('\n[AID_%s]\nvalue: %d\n' % (name.upper(), uid))

    # properties: everything of build.prop + default.prop that the build does not generate
    props = []
    for fn in ('build.prop', 'default.prop'):
        for l in Path(src, fn).read_text().splitlines():
            l = l.rstrip('\n')
            if not l or l.startswith('#'):
                continue
            k = l.split('=', 1)[0]
            if k == 'ro.zygote' or k.startswith(GEN_PROP_PREFIX):
                continue
            props.append((fn, l))
    with open(os.path.join(dst, 'vendor.prop'), 'w') as f:
        f.write('# Vendor properties of the stock firmware A605FNXXU8CVA1 that the build does not generate itself.\n')
        f.write('# Generated by gen_vendor.py from the stock build.prop and default.prop.\n')
        seen = set()
        for fn, l in props:
            k = l.split('=', 1)[0]
            if k in seen:
                continue
            seen.add(k)
            f.write(l + '\n')
        # Android 11 donor graphics stack (renamed *_a11): hw_get_module tries these first and falls back to
        # ro.board.platform, so the 32-bit stock HALs keep loading *.msm8953. PRODUCT_VENDOR_PROPERTIES does not
        # reach vendor/build.prop in this tree, hence they live here.
        f.write('# Graphics stack variant (Android 11 donor gralloc/composer).\n')
        f.write('ro.hardware.gralloc=a11\n')
        f.write('ro.hardware.hwcomposer=a11\n')

    # Android.mk: the SELinux files and the links/dirs module
    with open(os.path.join(dst, 'Android.mk'), 'w') as f:
        f.write('# Generated by gen_vendor.py. Do not edit.\n')
        f.write('LOCAL_PATH := $(call my-dir)\n\nifeq ($(TARGET_DEVICE),a6plte)\n\ninclude $(LOCAL_PATH)/runtime-policy.mk\n\n')
        f.write('# Symbolic links and empty directories of the stock vendor (PRODUCT_COPY_FILES can create neither).\n')
        f.write('include $(CLEAR_VARS)\nLOCAL_MODULE := a6plte_vendor_links\nLOCAL_MODULE_CLASS := ETC\n')
        f.write('LOCAL_MODULE_TAGS := optional\nLOCAL_VENDOR_MODULE := true\n')
        f.write('LOCAL_MODULE_STEM := a6plte_vendor_links.list\nLOCAL_SRC_FILES := links.list\n')
        f.write('LOCAL_POST_INSTALL_CMD := bash $(LOCAL_PATH)/make-links.sh $(LOCAL_PATH) $(TARGET_OUT_VENDOR)\n')
        f.write('include $(BUILD_PREBUILT)\n\n')
        f.write('''# Stock files that the build also has a rule for, and the Samsung SELinux policy.
#
# Two modules (or a module and PRODUCT_COPY_FILES) cannot install the same path (kati: "overriding commands for
# target"), and some stock files have the name of a module that Lineage builds from AOSP sources (the default HAL
# services and implementations: android.hardware.keymaster@3.0-service, ...). For those the Samsung build is the one
# that works with the rest of the stock vendor, so it is copied over the generated one after the build has installed
# everything under /vendor (installed-files-vendor.txt depends on all of it) and before vendor.img is made.
a6plte_overlay_files := %s
a6plte_selinux_files := %s
a6plte_remove_files := %s
include $(LOCAL_PATH)/arm64/build.mk
a6plte_overlay_stamp := $(PRODUCT_OUT)/obj/PACKAGING/a6plte_vendor_overlay_intermediates/copied.stamp
$(a6plte_overlay_stamp): PRIVATE_SRC := $(LOCAL_PATH)/proprietary
$(a6plte_overlay_stamp): PRIVATE_DST := $(TARGET_OUT_VENDOR)
$(a6plte_overlay_stamp): PRIVATE_OVERLAY := $(a6plte_overlay_files)
$(a6plte_overlay_stamp): PRIVATE_SELINUX := $(a6plte_selinux_files)
$(a6plte_overlay_stamp): PRIVATE_REMOVE := $(a6plte_remove_files)
$(a6plte_overlay_stamp): $(addprefix $(LOCAL_PATH)/proprietary/vendor/,$(a6plte_overlay_files)) $(addprefix $(LOCAL_PATH)/proprietary/selinux/,$(a6plte_selinux_files)) $(PRODUCT_OUT)/installed-files-vendor.txt $(a6plte_runtime_policy) $(a6plte_arm64_elf_checks)
\t@echo "Samsung vendor files over the generated ones: $(words $(PRIVATE_OVERLAY)) + $(words $(PRIVATE_SELINUX)) SELinux"
\t$(hide) mkdir -p $(PRIVATE_DST)/etc/selinux $(dir $@)
\t$(hide) for f in $(PRIVATE_OVERLAY); do mkdir -p $(PRIVATE_DST)/$$(dirname $$f); rm -f $(PRIVATE_DST)/$$f; cp -p $(PRIVATE_SRC)/vendor/$$f $(PRIVATE_DST)/$$f; done
\t$(hide) for f in $(PRIVATE_SELINUX); do rm -f $(PRIVATE_DST)/etc/selinux/$$f; cp $(PRIVATE_SRC)/selinux/$$f $(PRIVATE_DST)/etc/selinux/$$f; done
\t$(hide) for f in $(PRIVATE_REMOVE); do rm -f $(PRIVATE_DST)/$$f; done
\t$(hide) touch $@
$(PRODUCT_OUT)/vendor.img: $(a6plte_overlay_stamp)

''' % (' '.join(overlay), ' '.join(sorted(SELINUX_TOP)), ' '.join(LINEAGE_REMOVE)))
        f.write('''# boot.img ramdisk. The system image is system-as-root, so the build gives boot.img no ramdisk (BOARD_BUILD_SYSTEM_ROOT_IMAGE)
# and init_first_stage is not even defined; the kernel would find no /init. Samsung's bootloader/kernel expect what the
# stock boot image has: the static first-stage init (it mounts system from the dtb fstab and switches root to it) and
# dpolicy, with the mount points of an AOSP first-stage ramdisk. They are passed to mkbootimg with BOARD_MKBOOTIMG_ARGS
# (BoardConfigVendor.mk), which the build and releasetools (the boot.img of the zip) both use.
a6plte_ramdisk := $(PRODUCT_OUT)/obj/PACKAGING/a6plte_ramdisk_intermediates/ramdisk.img
$(a6plte_ramdisk): PRIVATE_SRC := $(LOCAL_PATH)/ramdisk
$(a6plte_ramdisk): $(LOCAL_PATH)/ramdisk/init $(LOCAL_PATH)/ramdisk/dpolicy $(HOST_OUT_EXECUTABLES)/mkbootfs $(HOST_OUT_EXECUTABLES)/minigzip
\t@echo "Samsung first-stage ramdisk: $@"
\t$(hide) rm -rf $(dir $@)root && mkdir -p $(dir $@)root/apex $(dir $@)root/debug_ramdisk $(dir $@)root/dev $(dir $@)root/mnt $(dir $@)root/proc $(dir $@)root/sys
\t$(hide) cp $(PRIVATE_SRC)/init $(PRIVATE_SRC)/dpolicy $(dir $@)root/ && chmod 750 $(dir $@)root/init && chmod 644 $(dir $@)root/dpolicy
\t$(hide) $(HOST_OUT_EXECUTABLES)/mkbootfs -d $(TARGET_OUT) $(dir $@)root | $(HOST_OUT_EXECUTABLES)/minigzip > $@
$(PRODUCT_OUT)/boot.img: $(a6plte_ramdisk)

''')
        f.write('endif\n')

    print('custom AIDs:', len(aids))
    print('xml not well-formed (copied by the overlay step):', bad_xml)
    print('copy', len(copies), 'overlay', len(overlay), 'lineage-built', len(skipped_aosp), 'toybox links dropped', dropped_links, 'selinux', len(selinux), 'links', len(links), 'empty dirs', len(dirs), 'props', len(seen))


GENERATED_OUTPUTS = (
    'proprietary', 'links.list', 'overlay.list', 'dirs.list', 'a6plte-vendor.mk',
    'vendor.prop', 'Android.mk', 'aids.fs', 'lineage_vendor_installs.txt',
)
SELINUX_FILES = (
    'plat_pub_versioned.cil', 'plat_sepolicy_vers.txt', 'vendor_file_contexts',
    'vendor_hwservice_contexts', 'vendor_mac_permissions.xml', 'vendor_property_contexts',
    'vendor_seapp_contexts', 'vendor_sepolicy.cil', 'vndservice_contexts',
)


def require_file(path):
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError('Required non-empty file missing: ' + str(path))


def disjoint(left, right):
    return left != right and left not in right.parents and right not in left.parents


@contextmanager
def staging_directory(parent):
    root = Path(tempfile.mkdtemp(prefix='.a6plte-vendor-', dir=parent))
    try:
        yield root
    finally:
        previous = root / 'previous'
        if previous.is_dir() and any(previous.iterdir()):
            # If rollback itself fails, keep the only copies of the old output.
            print('Previous output retained for recovery at: ' + str(previous), file=sys.stderr)
        else:
            shutil.rmtree(root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stock_vendor', type=Path)
    parser.add_argument('output_repo', type=Path)
    parser.add_argument('build_out', nargs='?', help='Build out directory, or none to keep the snapshot')
    parser.add_argument('stock_ramdisk', nargs='?', type=Path)
    args = parser.parse_args()
    src, dst = args.stock_vendor.resolve(), args.output_repo.resolve()
    try:
        if not src.is_dir() or not dst.is_dir():
            raise ValueError('Stock vendor and output repository must be existing directories')
        if not disjoint(src, dst):
            raise ValueError('Stock vendor and output repository must not overlap')
        build_out = None
        if args.build_out and args.build_out != 'none':
            build_out = Path(args.build_out).resolve()
            if not build_out.is_dir() or not disjoint(build_out, dst):
                raise ValueError('Build out must be an existing directory outside the output repository')
        ramdisk = args.stock_ramdisk.resolve() if args.stock_ramdisk else dst / 'ramdisk'
        if args.stock_ramdisk and not disjoint(ramdisk, dst):
            raise ValueError('External stock ramdisk and output repository must not overlap')
        for rel in ('build.prop', 'default.prop', 'etc/passwd', 'etc/fstab.qcom'):
            require_file(src / rel)
        for name in SELINUX_FILES:
            require_file(src / 'etc/selinux' / name)
        for name in ('init', 'dpolicy'):
            require_file(ramdisk / name)
        if build_out is None:
            require_file(dst / 'lineage_vendor_installs.txt')
        outputs = list(GENERATED_OUTPUTS)
        if args.stock_ramdisk:
            outputs.append('ramdisk')
        for name in outputs:
            if (dst / name).is_symlink():
                raise ValueError('Generated output must not be a symlink: ' + str(dst / name))

        # Generation/patch/XML errors only affect this private staging tree.
        with staging_directory(dst.parent) as root:
            stage, previous = root / 'generated', root / 'previous'
            stage.mkdir(); previous.mkdir()
            for name in ('patches', 'policy', 'ramdisk', 'lineage_vendor_installs.txt'):
                source = dst / name
                if source.is_dir():
                    shutil.copytree(source, stage / name)
                elif source.is_file():
                    shutil.copy2(source, stage / name)
            generate(str(src), str(stage), str(build_out) if build_out else None,
                     str(ramdisk) if args.stock_ramdisk else None)
            for name in outputs:
                if not (stage / name).exists():
                    raise ValueError('Generator did not produce: ' + name)
            # Each replacement is atomic. Roll back already replaced paths on a Python/IO error.
            # A power loss during the multi-file publication still requires manual recovery.
            installed, moved = [], []
            try:
                for name in outputs:
                    if (dst / name).exists():
                        os.replace(dst / name, previous / name)
                        moved.append(name)
                    os.replace(stage / name, dst / name)
                    installed.append(name)
            except BaseException:
                for name in reversed(installed):
                    os.replace(dst / name, stage / name)
                for name in reversed(moved):
                    os.replace(previous / name, dst / name)
                raise
            shutil.rmtree(previous)
    except (OSError, ValueError, subprocess.CalledProcessError, AssertionError) as error:
        parser.exit(1, 'ERROR: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
