"""Prepare NEW Jenkins storage and a daemon-visible deploy path. Never reset existing Jenkins."""
import json
import subprocess
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent


def docker(*args):
    return subprocess.run(['docker', *args], check=True, capture_output=True, text=True).stdout.strip()


if __name__ == '__main__':
    if 'app-net' not in docker('network', 'ls', '--format', '{{.Name}}').splitlines():
        docker('network', 'create', 'app-net')
    docker('volume', 'create', '--label', 'com.docker.compose.project=telu-jenkins',
           '--label', 'com.docker.compose.volume=telu-jenkins-deploy', 'telu-jenkins-deploy')
    target = docker('volume', 'inspect', 'telu-jenkins-deploy', '--format', '{{.Mountpoint}}')
    if not PurePosixPath(target).is_absolute() or not target.endswith('/telu-jenkins-deploy/_data'):
        raise RuntimeError('Unexpected deploy path; check the Docker volume before continuing')
    content = f'TELU_DEPLOY_DIR={target}\nDOCKER_SOCKET_GID=0\n'
    env_path = ROOT / '.env'
    if env_path.exists() and env_path.read_text() != content:
        raise RuntimeError('Existing Jenkins configuration differs; refusing to overwrite it')
    env_path.write_text(content, encoding='utf-8')
    print('Jenkins baru: http://localhost:8082')
    print('DEPLOY_DIR untuk parameter job:', target)
    print('Konfigurasi siap. Jalankan docker compose up -d --build di folder jenkins ini.')
