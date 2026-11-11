"""Validate locally packaged candidate images before Docker/Jenkins deployment."""
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(root=ROOT):
    frontend = (root / 'frontend').resolve()
    candidates = json.loads((root / 'config.json').read_text(encoding='utf-8'))['candidates']
    if [c['option'] for c in candidates] != ['A', 'B']:
        raise ValueError('Candidate API options must remain A and B')
    count = 0
    for candidate in candidates:
        if len(candidate['people']) != 2 or not all(person['name'] and person['role'] for person in candidate['people']):
            raise ValueError('Each candidate requires a chair and deputy with text labels')
        for key in ('pair', 'chair', 'deputy', 'poster'):
            path = (frontend / candidate['assets'][key]).resolve()
            if not path.is_relative_to(frontend):
                raise ValueError('Candidate assets must be local frontend files')
            content = path.read_bytes()
            if content[:8] != b'\x89PNG\r\n\x1a\n' or content[12:16] != b'IHDR':
                raise ValueError(f'Invalid PNG: {path.name}')
            width, height = struct.unpack('>II', content[16:24])
            if not width or not height:
                raise ValueError(f'Invalid dimensions: {path.name}')
            if key != 'poster' and content[25] not in (4, 6):
                raise ValueError(f'Expected alpha channel: {path.name}')
            count += 1
    return count


if __name__ == '__main__':
    print(f'PASS: {check()} local candidate PNG assets, identity labels, and A/B mapping.')
