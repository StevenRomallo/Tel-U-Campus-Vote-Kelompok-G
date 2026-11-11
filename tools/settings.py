"""Read local runtime configuration without printing credentials."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_env(path=None):
    path = Path(path or ROOT / '.env')
    values = {}
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            if not line.strip() or line.lstrip().startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            value = value.strip()
            if value.startswith('"') and value.endswith('"'):
                value = json.loads(value)
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            values[key.strip()] = value
    return values


def runtime_config():
    return dict(read_env(), **{key:value for key,value in os.environ.items() if key in {'NIM_HMAC_SECRET','LOGIN_PASSWORD','ADMIN_TOKEN','COOKIE_SECURE','APP_PORT'}})
