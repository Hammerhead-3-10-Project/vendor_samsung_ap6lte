#!/usr/bin/env python3
"""Fetch pinned blob candidates into an external directory for offline review."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    repo, commit = manifest['repo'], manifest['commit']
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        parser.error('Invalid source repository')
    if not re.fullmatch(r'[a-f0-9]{40}', commit):
        parser.error('Source must be pinned to a full commit SHA')
    destination = args.destination.resolve()
    repository = Path(__file__).resolve().parent.parent
    if destination == repository or repository in destination.parents:
        parser.error('Use a scratch directory outside the vendor repository')
    for entry in manifest['files']:
        relative = PurePosixPath(entry['path'])
        if relative.is_absolute() or '..' in relative.parts or str(relative) in ('', '.'):
            parser.error('Invalid relative blob path')
        target = destination.joinpath(*relative.parts)
        if target.is_symlink() or destination not in target.resolve().parents:
            parser.error('Destination path escapes scratch directory')
        if target.exists():
            data = target.read_bytes()
        else:
            url = f'https://raw.githubusercontent.com/{repo}/{commit}/{relative}'
            with urllib.request.urlopen(url, timeout=60) as response:
                data = response.read()
        git_hash = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if (len(data) != entry['size'] or git_hash != entry['git_blob']
                or hashlib.sha256(data).hexdigest() != entry['sha256']):
            raise RuntimeError(f'Integrity mismatch; existing files are never replaced: {target}')
        if (data[:4] != b'\x7fELF' or data[4] * 32 != entry['bits']
                or data[5] != 1 or int.from_bytes(data[18:20], 'little') != entry['machine']):
            raise RuntimeError(f'Unexpected ELF architecture: {target}')
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(data)
                # Publish only if absent: do not overwrite a concurrent user's file.
                os.link(temporary, target)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        print(f'Verified ELF{entry["bits"]}: {relative}')
    print(f'{len(manifest["files"])} candidates verified; no build configuration changed.')


if __name__ == '__main__':
    main()
