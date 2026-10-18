#!/usr/bin/env python3
"""Regenerating stock vendor must preserve the ARM64 layer and product zygote."""
from pathlib import Path
import subprocess
import tempfile
import unittest

GENERATOR = Path(__file__).resolve().parents[1] / 'gen_vendor.py'


class Arm64Regeneration(unittest.TestCase):
    def test_two_stock_regenerations_preserve_native_layer_and_legacy_blobs(self):
        with tempfile.TemporaryDirectory(prefix='a6plte-arm64-generator-') as temp:
            root = Path(temp)
            stock, repo = root / 'stock', root / 'vendor'
            files = {
                'build.prop': 'ro.board.platform=msm8953\nro.zygote=zygote32\n',
                'default.prop': 'ro.zygote=zygote32\nro.bionic.arch=arm\nro.bionic.2nd_arch=\ndalvik.vm.isa.arm.variant=cortex-a53\npersist.sys.usb.config=mtp\n',
                'etc/passwd': 'vendor_test:x:2901:2901::/:/system/bin/sh\n',
                'etc/fstab.qcom': '/dev/block/userdata /data ext4 defaults wait,forceencrypt=footer\n',
                'lib/legacy.so': 'stock ARM32 sentinel',
            }
            policy_files = ('plat_pub_versioned.cil', 'plat_sepolicy_vers.txt', 'vendor_file_contexts',
                            'vendor_hwservice_contexts', 'vendor_mac_permissions.xml',
                            'vendor_property_contexts', 'vendor_seapp_contexts', 'vendor_sepolicy.cil',
                            'vndservice_contexts')
            files.update({'etc/selinux/' + name: 'stock policy\n' for name in policy_files})
            for relative, content in files.items():
                p = stock / relative
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content)
            (repo / 'ramdisk').mkdir(parents=True)
            for name in ('init', 'dpolicy'):
                (repo / 'ramdisk' / name).write_text('stock ramdisk')
            (repo / 'lineage_vendor_installs.txt').write_text('lib/source.so\n')
            layer = repo / 'arm64/blobs/lib64/native.so'
            layer.parent.mkdir(parents=True)
            layer.write_bytes(b'ARM64 layer sentinel')
            (repo / 'arm64/build.mk').write_text('# source graphics overlay exclusions\n')
            for _ in range(2):
                result = subprocess.run(['python3', str(GENERATOR), str(stock), str(repo)],
                                        capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertNotIn('ro.zygote=', (repo / 'vendor.prop').read_text())
                self.assertNotIn('ro.bionic.', (repo / 'vendor.prop').read_text())
                self.assertNotIn('dalvik.vm.isa.', (repo / 'vendor.prop').read_text())
                self.assertIn('persist.sys.usb.config=mtp', (repo / 'vendor.prop').read_text())
                self.assertEqual(layer.read_bytes(), b'ARM64 layer sentinel')
                self.assertEqual((repo / 'proprietary/vendor/lib/legacy.so').read_text(),
                                 'stock ARM32 sentinel')
                self.assertIn('include $(LOCAL_PATH)/arm64/build.mk', (repo / 'Android.mk').read_text())


if __name__ == '__main__':
    unittest.main()
