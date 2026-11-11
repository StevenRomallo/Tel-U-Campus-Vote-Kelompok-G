"""Bounded health check through the same origin used by visitors."""
import argparse
import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def check(base, attempts, delay):
    for attempt in range(1, attempts + 1):
        try:
            with urlopen(base.rstrip('/') + '/health', timeout=4) as response:
                data = json.load(response)
                if data.get('status') != 'ok':
                    raise ValueError('Health status is not ok')
            for path in ('/login.html', '/index.html', '/dashboard.html', '/config', '/votes'):
                with urlopen(base.rstrip('/') + path, timeout=4) as response:
                    if response.status != 200:
                        raise ValueError('Unexpected status: ' + path)
            print('PASS: health, frontend pages, configuration, and votes endpoint.')
            return True
        except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
            print(f'Attempt {attempt}/{attempts}: {type(exc).__name__}: {exc}')
            if attempt < attempts:
                time.sleep(delay)
    return False


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8097')
    parser.add_argument('--attempts', type=int, default=12)
    parser.add_argument('--delay', type=float, default=3)
    args = parser.parse_args()
    if args.attempts < 1 or args.delay < 0:
        parser.error('attempts >= 1 and delay >= 0 required')
    raise SystemExit(0 if check(args.url, args.attempts, args.delay) else 1)
