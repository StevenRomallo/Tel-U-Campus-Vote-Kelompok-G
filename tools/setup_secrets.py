"""Generate persistent local secrets once; retain existing values on subsequent runs."""
import json
import os
import secrets
from settings import ROOT, read_env


def setup():
    path = ROOT / '.env'
    values = read_env(path)
    for key in ('NIM_HMAC_SECRET','ADMIN_TOKEN'):
        if not values.get(key):
            values[key] = os.environ.get(key) or secrets.token_hex(32)
    if len(values['NIM_HMAC_SECRET']) < 32:
        raise ValueError('Existing NIM_HMAC_SECRET too short. Restore a valid, original key.')
    values.setdefault('LOGIN_PASSWORD','12345678')
    values.setdefault('COOKIE_SECURE','false')
    values.setdefault('APP_PORT','8097')
    values.setdefault('ENABLE_DEMO_TOOLS','false')
    temporary = path.with_name('.env.next')
    temporary.write_text('\n'.join(key+'='+json.dumps(value) for key,value in values.items())+'\n',encoding='utf-8')
    if os.name != 'nt':
        temporary.chmod(0o600)
    os.replace(temporary,path)
    print('Konfigurasi lokal siap. Secret yang sudah ada dipertahankan; nilainya tidak ditampilkan.')


if __name__ == '__main__':
    setup()
