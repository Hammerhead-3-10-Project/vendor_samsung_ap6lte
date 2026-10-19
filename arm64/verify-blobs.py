#!/usr/bin/env python3
"""Reject missing/corrupt/wrong-ABI native blobs before vendor packaging."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', action='store_true', help='Print relative build prerequisites')
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'selected-blobs.json').read_text())
    if args.inputs:
        fix = {f['path']: f for f in json.loads((ROOT / 'blob-fixups.json').read_text())['fixups']}
        print(' '.join(fix.get(e['path'], {}).get('install_path', e['path']) for e in manifest['files']))
        return
    fixups = {f['path']: f for f in json.loads((ROOT / 'blob-fixups.json').read_text())['fixups']}
    for entry in manifest['files']:
        relative = entry['path']
        fixup = fixups.get(relative)
        if fixup and fixup['source_sha256'] != entry['sha256']:
            raise RuntimeError('Fixup source fingerprint mismatch: ' + relative)
        expected = fixup['patched_sha256'] if fixup else entry['sha256']
        data = (ROOT / 'blobs' / (fixup.get('install_path', relative) if fixup else relative)).read_bytes()
        if (data[:6] != b'\x7fELF\x02\x01' or int.from_bytes(data[18:20], 'little') != 183
                or hashlib.sha256(data).hexdigest() != expected):
            raise RuntimeError('ARM64 blob integrity/architecture mismatch: ' + relative)
    print(f'Verified {len(manifest["files"])} pinned AArch64 blobs, including reviewed fixups.')


if __name__ == '__main__':
    main()
