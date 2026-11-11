"""Verify server-pushed updates through Nginx, using one explicitly created test UUID."""
import argparse
import json
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from client import Client


def request(base, path, method='GET', body=None):
    req = Request(base.rstrip('/') + path, method=method, data=None if body is None else json.dumps(body).encode(), headers={'Content-Type':'application/json'})
    with urlopen(req, timeout=5) as response:
        return json.load(response)


def next_event(response):
    while True:
        line = response.readline().decode().strip()
        if line.startswith('data:'):
            return json.loads(line[len('data:'):])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8137')
    parser.add_argument('--confirm-test-vote', action='store_true')
    args = parser.parse_args()
    if not args.confirm_test_vote:
        parser.error('Use --confirm-test-vote to add and remove exactly one test record')
    own_id = None
    client=Client(args.url)
    client.fresh_test_identity()
    try:
        with urlopen(args.url.rstrip('/') + '/events', timeout=5) as stream:
            assert 'text/event-stream' in stream.headers['Content-Type']
            initial = next_event(stream)
            started = time.monotonic()
            receipt = client.call('/votes','POST',{'option':'A','faculty':'Informatika','program':'S1 Informatika','cohort':2024},expected=201)['vote']
            own_id = receipt['id']
            changed = next_event(stream)
            elapsed = (time.monotonic() - started) * 1000
            assert changed['revision'] != initial['revision']
            assert set(changed) == {'revision'}, 'Stream must not contain voter data'
            rows = request(args.url, '/votes')['votes']
            own_row = next(row for row in rows if row['id'] == own_id)
            assert set(own_row) == {'id','alias','index','created_at','is_demo'}
            print(f'PASS: notification received {elapsed:.0f} ms after POST began (no polling).')
            print('PASS: public record contains only alias, opaque ID, index, time, and demo marker.')
    finally:
        if own_id:
            rows = request(args.url, '/votes')['votes']
            own_row = next(row for row in rows if row['id'] == own_id)
            removed = client.call('/votes?' + urlencode({'index':own_row['index'],'id':own_id}), 'DELETE',admin=True)
            assert removed['deleted_id'] == own_id
            print('Removed only this invocation\'s test UUID:', own_id)


if __name__ == '__main__':
    main()
