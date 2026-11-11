"""Acceptance check: recreate only this project's backend; preserve all pre-existing votes."""
import argparse
import json
import subprocess
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from client import Client

ROOT = Path(__file__).resolve().parents[1]


def call(base, path, method='GET', body=None):
    request = Request(base.rstrip('/') + path, method=method, data=None if body is None else json.dumps(body).encode(), headers={'Content-Type':'application/json'})
    with urlopen(request, timeout=5) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8137')
    parser.add_argument('--project',required=True)
    parser.add_argument('--compose-override',required=True)
    parser.add_argument('--confirm-container-recreate', action='store_true')
    args = parser.parse_args()
    if not args.confirm_container_recreate:
        parser.error('--confirm-container-recreate is required; backend will be unavailable briefly')
    client=Client(args.url)
    test_nim=client.fresh_test_identity()
    compose=['docker','compose','--project-directory',str(ROOT),'-p',args.project,'-f',str(ROOT/'docker-compose.yml'),'-f',str(Path(args.compose_override).resolve())]
    manifest=json.loads(subprocess.run(compose+['config','--format','json'],capture_output=True,text=True,check=True).stdout)
    volume=manifest['volumes']['polling-db-data']['name']
    if args.project=='telu-campus-vote' or volume=='polling-db-data' or not volume.startswith('telu-auth-qa-data-'):
        raise RuntimeError('Refusing to recreate a backend unless its volume is explicitly isolated QA storage')
    before = client.call('/votes')['votes']
    original_ids = {r['id'] for r in before}
    receipt=client.call('/votes','POST',{'option':'B','faculty':'Informatika','program':'S1 Informatika','cohort':2024},expected=201)
    test_vote=receipt['vote']
    print('Created ONE acceptance-test vote:', test_vote['id'], flush=True)
    subprocess.run(compose+['rm','--stop','--force','backend'],cwd=ROOT,check=True)
    subprocess.run(compose+['up','-d','--no-build','--wait','--wait-timeout','90','backend'],cwd=ROOT,check=True)
    last_error = None
    for _ in range(20):
        try:
            after = call(args.url, '/votes')['votes']
            break
        except Exception as exc:
            last_error = exc
            time.sleep(1)
    else:
        raise RuntimeError('Nginx/backend did not recover') from last_error
    remaining_ids = {r['id'] for r in after}
    assert original_ids.issubset(remaining_ids), 'Pre-existing records missing'
    assert test_vote['id'] in remaining_ids, 'Acceptance vote did not survive backend removal'
    status=client.login(test_nim)
    assert status['has_voted'] and status['voted_at']==receipt['voted_at']
    client.call('/votes','POST',{'option':'A','faculty':'Informatika','program':'S1 Informatika','cohort':2024},expected=409)
    print('PASS: records and NIM participation survived backend recreation; duplicate vote rejected.',flush=True)
    # Delete exactly the UUID created by THIS invocation. Never loop over user records.
    own_row = next(row for row in after if row['id'] == test_vote['id'])
    deleted = client.call('/votes?' + urlencode({'index':own_row['index'], 'id':test_vote['id']}), 'DELETE',admin=True)
    assert deleted['deleted_id'] == test_vote['id']
    final = call(args.url, '/votes')['votes']
    assert {r['id'] for r in final} == original_ids, 'Dataset changed during acceptance check'
    assert client.call('/auth/me')['has_voted']
    print('PASS: only the acceptance-test UUID removed; its participation marker remains locked.',flush=True)


if __name__ == '__main__':
    main()
