"""Stage tracked deploy files in a persistent, host-visible directory. Never touch data volumes."""
import argparse
import os
import shutil
import json
from pathlib import Path
from settings import runtime_config, read_env

ROOT = Path(__file__).resolve().parents[1]


def prepare(directory, port, demo):
    target = Path(directory)
    if not target.is_absolute() or str(target) == target.anchor:
        raise ValueError('Deployment requires an absolute, non-root directory')
    if not 1024 <= int(port) <= 65535:
        raise ValueError('Port must be between 1024 and 65535')
    target.mkdir(parents=True, exist_ok=True)
    if target.resolve() == ROOT:
        raise ValueError('Deployment directory must differ from the Jenkins checkout')
    # Copy without recursive deletion. Unreferenced old assets are harmless.
    for filename in ('docker-compose.yml',):
        shutil.copy2(ROOT / filename, target / filename)
    for folder in ('frontend', 'nginx'):
        shutil.copytree(ROOT / folder, target / folder, dirs_exist_ok=True)
    def quoted(value):
        return '"' + str(value).replace('\\', '/').replace('$', '$$').replace('"', '\\"') + '"'
    values = runtime_config()
    previous = read_env(target / '.env')
    if previous.get('NIM_HMAC_SECRET') and previous['NIM_HMAC_SECRET'] != values.get('NIM_HMAC_SECRET'):
        raise ValueError('Deployment secret differs from the existing key. Restore the original key; never reset participation.')
    if len(values.get('NIM_HMAC_SECRET','')) < 32:
        raise ValueError('Provide the persistent NIM_HMAC_SECRET through Jenkins Credentials or local .env')
    text = '\n'.join([
        f'APP_PORT={int(port)}',
        f'ENABLE_DEMO_TOOLS={str(demo).lower()}',
        'FRONTEND_HOST_PATH=' + quoted(target / 'frontend'),
        'NGINX_HOST_PATH=' + quoted(target / 'nginx' / 'default.conf'),
        'NIM_HMAC_SECRET=' + json.dumps(values['NIM_HMAC_SECRET']),
        'ADMIN_TOKEN=' + json.dumps(values.get('ADMIN_TOKEN','')),
        'LOGIN_PASSWORD=' + json.dumps(values.get('LOGIN_PASSWORD','12345678')),
        'COOKIE_SECURE=' + json.dumps(values.get('COOKIE_SECURE','false')),
        '',
    ])
    temporary = target / '.env.next'
    temporary.write_text(text, encoding='utf-8')
    if os.name != 'nt':
        temporary.chmod(0o600)
    os.replace(temporary, target / '.env')
    # Compose validates build.context even when deployment uses --no-build.
    shutil.copy2(ROOT / 'Dockerfile', target / 'Dockerfile')
    print('Deployment assets prepared:', target)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', required=True)
    parser.add_argument('--port', type=int, default=8097)
    parser.add_argument('--demo', choices=('true', 'false'), default='false')
    args = parser.parse_args()
    prepare(args.directory, args.port, args.demo)
