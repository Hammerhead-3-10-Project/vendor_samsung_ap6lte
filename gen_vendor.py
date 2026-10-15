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
import os, shutil, sys

src, dst = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
LINEAGE_OUT = os.path.abspath(sys.argv[3]) if len(sys.argv) > 3 else None   # out/ of a Lineage build (to refresh the snapshot)
INSTALLS = os.path.join(dst, 'lineage_vendor_installs.txt')
if LINEAGE_OUT:
    # Every file the Lineage build has a rule for under /vendor (Soong and Android.mk modules), from the ninja files.
    import glob, re
    pat = re.compile(r'out/target/product/[^/\s:$|]+/vendor/[^\s:$|]+')
    found = set()
    for f in glob.glob(LINEAGE_OUT + '/*.ninja') + [LINEAGE_OUT + '/soong/build.ninja']:
        if not os.path.isfile(f):
            continue
        for line in open(f, errors='ignore'):
            if line.startswith('build ') and '/vendor/' in line:
                for m in pat.findall(line.split(':')[0]):
                    found.add(m.split('/vendor/', 1)[1])
    open(INSTALLS, 'w').write('\n'.join(sorted(found)) + '\n')
lineage_installs = set(open(INSTALLS).read().split()) if os.path.exists(INSTALLS) else set()
PATH = 'vendor/samsung/a6plte'

# Files the build generates itself from tracked sources (manifest/matrix from the device tree, fs_config from
# config.fs, build.prop/default.prop from the board config + vendor.prop) or that are only placeholders.
GENERATED = {'build.prop', 'default.prop', 'etc/vintf/manifest.xml', 'etc/vintf/compatibility_matrix.xml',
             'etc/fs_config_dirs', 'etc/fs_config_files'}
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
LINEAGE_REMOVE = ['etc/init/rild.legacy.rc', 'etc/init/android.hardware.media.omx@1.0-service.rc']
LINK_TARGETS_LINEAGE = {'toybox_vendor', 'toolbox', 'grep'}   # the toybox applet links are created by the toybox_vendor module

# properties the build writes into vendor/build.prop itself
GEN_PROP_PREFIX = ('ro.vendor.build.date', 'ro.vendor.build.fingerprint', 'ro.vendor.build.id', 'ro.vendor.build.tags',
                   'ro.vendor.build.type', 'ro.vendor.build.version.incremental', 'ro.vendor.build.version.release',
                   'ro.vendor.build.version.sdk', 'ro.vendor.build.security_patch',   # VENDOR_SECURITY_PATCH
                   'ro.product.vendor.', 'ro.vendor.product.cpu.', 'ro.bootimage.build.',
                   'ro.product.first_api_level', 'ro.product.board', 'ro.board.platform')
# NOT generated and kept: ro.vendor.build.version.sehi (Samsung)

for d in ('proprietary',):
    shutil.rmtree(os.path.join(dst, d), ignore_errors=True)
copies, overlay, skipped_aosp, selinux, links, dirs = [], [], [], [], [], []
for root, dnames, fnames in os.walk(src):
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
for root, dnames, fnames in os.walk(src):
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
before = len(links)
links = [(p, t) for p, t in links if not (os.path.basename(t) in LINK_TARGETS_LINEAGE)]
dropped_links = before - len(links)
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
    f.write('# init compiles the policy at boot (plat from system + the Samsung vendor policy). A precompiled policy built\n')
    f.write('# here would use the stub types of sepolicy/ and must not exist.\n')
    f.write('PRODUCT_PRECOMPILED_SEPOLICY := false\n')

# custom users/groups of the stock vendor (etc/passwd, uid in the OEM ranges): the build only accepts them in init
# scripts (host_init_verifier) if they are declared as AIDs. aids.fs is added to TARGET_FS_CONFIG_GEN.
aids = []
for l in open(os.path.join(src, 'etc/passwd')):
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
    for l in open(os.path.join(src, fn)):
        l = l.rstrip('\n')
        if not l or l.startswith('#'):
            continue
        k = l.split('=', 1)[0]
        if k.startswith(GEN_PROP_PREFIX):
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

# Android.mk: the SELinux files and the links/dirs module
with open(os.path.join(dst, 'Android.mk'), 'w') as f:
    f.write('# Generated by gen_vendor.py. Do not edit.\n')
    f.write('LOCAL_PATH := $(call my-dir)\n\nifeq ($(TARGET_DEVICE),a6plte)\n\n')
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
a6plte_overlay_stamp := $(PRODUCT_OUT)/obj/PACKAGING/a6plte_vendor_overlay_intermediates/copied.stamp
$(a6plte_overlay_stamp): PRIVATE_SRC := $(LOCAL_PATH)/proprietary
$(a6plte_overlay_stamp): PRIVATE_DST := $(TARGET_OUT_VENDOR)
$(a6plte_overlay_stamp): PRIVATE_OVERLAY := $(a6plte_overlay_files)
$(a6plte_overlay_stamp): PRIVATE_SELINUX := $(a6plte_selinux_files)
$(a6plte_overlay_stamp): PRIVATE_REMOVE := $(a6plte_remove_files)
$(a6plte_overlay_stamp): $(addprefix $(LOCAL_PATH)/proprietary/vendor/,$(a6plte_overlay_files)) $(addprefix $(LOCAL_PATH)/proprietary/selinux/,$(a6plte_selinux_files)) $(PRODUCT_OUT)/installed-files-vendor.txt
\t@echo "Samsung vendor files over the generated ones: $(words $(PRIVATE_OVERLAY)) + $(words $(PRIVATE_SELINUX)) SELinux"
\t$(hide) mkdir -p $(PRIVATE_DST)/etc/selinux $(dir $@)
\t$(hide) for f in $(PRIVATE_OVERLAY); do mkdir -p $(PRIVATE_DST)/$$(dirname $$f); rm -f $(PRIVATE_DST)/$$f; cp -p $(PRIVATE_SRC)/vendor/$$f $(PRIVATE_DST)/$$f; done
\t$(hide) for f in $(PRIVATE_SELINUX); do rm -f $(PRIVATE_DST)/etc/selinux/$$f; cp $(PRIVATE_SRC)/selinux/$$f $(PRIVATE_DST)/etc/selinux/$$f; done
\t$(hide) for f in $(PRIVATE_REMOVE); do rm -f $(PRIVATE_DST)/$$f; done
\t$(hide) touch $@
$(PRODUCT_OUT)/vendor.img: $(a6plte_overlay_stamp)

''' % (' '.join(overlay), ' '.join(sorted(SELINUX_TOP)), ' '.join(LINEAGE_REMOVE)))
    f.write('endif\n')

print('custom AIDs:', len(aids))
print('xml not well-formed (copied by the overlay step):', bad_xml)
print('copy', len(copies), 'overlay', len(overlay), 'lineage-built', len(skipped_aosp), 'toybox links dropped', dropped_links, 'selinux', len(selinux), 'links', len(links), 'empty dirs', len(dirs), 'props', len(seen))
