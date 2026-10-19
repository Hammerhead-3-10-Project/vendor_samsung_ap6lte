#!/usr/bin/env python3
"""Refresh ARM64 blobs from a verified donor cache and apply reviewed fixups."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent


def executable_sections(data):
    """Compare actual instruction sections, independently of dynamic metadata."""
    offset = struct.unpack_from('<Q', data, 40)[0]
    size, count, strings_index = struct.unpack_from('<HHH', data, 58)
    sections = [struct.unpack_from('<IIQQQQIIQQ', data, offset + i * size) for i in range(count)]
    header = sections[strings_index]
    names = data[header[4]:header[4] + header[5]]
    return {names[s[0]:].split(b'\0', 1)[0]: data[s[4]:s[4] + s[5]]
            for s in sections if s[2] & 4}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('donor_cache', type=Path)
    parser.add_argument('--patchelf', required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'selected-blobs.json').read_text())
    config = json.loads((ROOT / 'blob-fixups.json').read_text())
    fixups = {f['path']: f for f in config['fixups']}
    with tempfile.TemporaryDirectory(prefix='.arm64-refresh-', dir=ROOT.parent.parent) as temporary:
        prepared = []
        for entry in manifest['files']:
            relative = entry['path']
            data = (args.donor_cache / relative).read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
            if digest != entry['sha256'] or blob != entry['git_blob'] or len(data) != entry['size']:
                raise RuntimeError('Upstream integrity mismatch: ' + relative)
            if data[:6] != b'\x7fELF\x02\x01' or int.from_bytes(data[18:20], 'little') != 183:
                raise RuntimeError('Expected AArch64 ELF: ' + relative)
            staged = Path(temporary) / relative
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes(data)
            if relative in fixups:
                fixup = fixups[relative]
                if digest != fixup['source_sha256']:
                    raise RuntimeError('Fixup source mismatch: ' + relative)
                command = [str(args.patchelf)]
                if fixup.get('add_needed'):
                    command += ['--add-needed', fixup['add_needed']]
                if fixup.get('set_soname'):
                    command += ['--set-soname', fixup['set_soname']]
                for old, new in sorted(fixup.get('replace_needed', {}).items()):
                    command += ['--replace-needed', old, new]
                subprocess.run(command + [str(staged)], check=True)
                patched = staged.read_bytes()
                if hashlib.sha256(patched).hexdigest() != fixup['patched_sha256']:
                    raise RuntimeError('Patched hash differs; review the patchelf version: ' + relative)
                if executable_sections(data) != executable_sections(patched):
                    raise RuntimeError('Executable section changed: ' + relative)
            prepared.append((staged, ROOT / 'blobs' / fixup.get('install_path', relative) if relative in fixups else ROOT / 'blobs' / relative))
        # Validate the entire set before replacing any tracked blob. Run while builds are idle.
        for source, destination in prepared:
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, destination)
    print(f'Refreshed {len(prepared)} verified ARM64 blobs; instruction sections unchanged by fixups.')


if __name__ == '__main__':
    main()
