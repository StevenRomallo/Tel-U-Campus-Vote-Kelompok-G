"""Development preview with the same persisted secrets as Docker."""
import argparse
import sys
from settings import ROOT, runtime_config

sys.path.insert(0,str(ROOT))
import app

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--data-dir',default=str(ROOT/'data'))
    parser.add_argument('--demo-tools',action='store_true')
    args = parser.parse_args()
    values = runtime_config()
    server = app.make_server(port=args.port,data_dir=args.data_dir,serve_frontend=True,demo_tools=args.demo_tools,hmac_secret=values.get('NIM_HMAC_SECRET'),login_password=values.get('LOGIN_PASSWORD','12345678'),admin_token=values.get('ADMIN_TOKEN',''),cookie_secure=values.get('COOKIE_SECURE','false').lower()=='true')
    print(f'Tel-U Campus Vote: http://127.0.0.1:{args.port}',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
