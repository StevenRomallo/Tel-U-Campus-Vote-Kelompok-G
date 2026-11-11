"""Persistence, migration, authenticated voting, privacy, and live integration tests."""
import contextlib
import io
import json
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.cookiejar import CookieJar
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen, build_opener, HTTPCookieProcessor
import app

KEY = 'test-only-hmac-secret-not-for-deployment-00000000'
ADMIN = 'test-only-operator-token'
PASSWORD = '12345678'


def nim(number=1):
    return '1010' + f'{number:08d}'


def digest(number=1):
    return app.nim_digest(nim(number), KEY)


def payload(option='A', cohort=2024, **extra):
    return dict(option=option, cohort=cohort, faculty='Informatika', program='S1 Informatika', **extra)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = app.VoteStore(self.tmp.name, KEY)

    def test_nim_format_and_ascii(self):
        self.assertEqual(app.normalize_nim(' 101012345678 '),'101012345678')
        for value in (None, 101012345678, '10101234567', '1010123456789', '201012345678', '1010abcdefgh', '1010１２３４５６７８', '1010 12345678'):
            with self.subTest(value=value), self.assertRaises(app.APIError):
                app.normalize_nim(value)

    def test_atomic_vote_and_first_timestamp(self):
        self.assertFalse(self.store.status(digest())['has_voted'])
        first = self.store.add(payload(),digest())
        self.assertEqual(self.store.status(digest())['voted_at'],first['created_at'])
        with self.assertRaises(app.APIError) as error:
            self.store.add(payload('B'),digest())
        self.assertEqual(error.exception.status,409)
        self.assertEqual(error.exception.details['voted_at'],first['created_at'])
        self.assertEqual(len(self.store.snapshot()),1)
        self.assertEqual(self.store.revision,1)

    def test_parallel_same_nim_only_one_success(self):
        def attempt(_):
            try:
                self.store.add(payload(),digest())
                return 201
            except app.APIError as exc:
                return exc.status
        with ThreadPoolExecutor(max_workers=12) as executor:
            statuses=list(executor.map(attempt,range(20)))
        self.assertEqual(statuses.count(201),1)
        self.assertEqual(statuses.count(409),19)
        self.assertEqual(self.store.revision,1)

    def test_parallel_distinct_nims_no_lost_votes(self):
        with ThreadPoolExecutor(max_workers=12) as executor:
            list(executor.map(lambda index:self.store.add(payload(),digest(index)),range(40)))
        self.assertEqual(len(self.store.snapshot()),40)
        document=json.loads(self.store.path.read_text())
        self.assertEqual(len(document['used_nims']),40)

    def test_restart_and_delete_preserve_participation(self):
        vote=self.store.add(payload(),digest())
        self.store.delete(0,vote['id'])
        restored=app.VoteStore(self.tmp.name,KEY)
        self.assertEqual(restored.snapshot(),[])
        self.assertEqual(restored.status(digest())['voted_at'],vote['created_at'])
        with self.assertRaises(app.APIError) as error:
            restored.add(payload(),digest())
        self.assertEqual(error.exception.status,409)

    def test_invalid_payload_does_not_reserve_nim(self):
        for invalid in ({'option':'C'},{'cohort':True},{'cohort':'2024'},{'program':'S1 Akuntansi'},{'campus':'Jakarta'}):
            body=payload();body.update(invalid)
            with self.assertRaises(app.APIError):
                self.store.add(body,digest())
            self.assertFalse(self.store.status(digest())['has_voted'])
        self.assertEqual(self.store.revision,0)

    def test_failed_disk_write_does_not_reserve_nim(self):
        with patch.object(self.store,'_write',side_effect=OSError('simulated disk failure')):
            with self.assertRaises(OSError):
                self.store.add(payload(),digest())
        self.assertFalse(self.store.status(digest())['has_voted'])
        self.assertEqual(self.store.snapshot(),[])
        self.assertEqual(self.store.revision,0)
        self.store.add(payload(),digest())

    def test_corrupt_file_preserved(self):
        self.store.path.write_text('{broken',encoding='utf-8')
        with self.assertRaises(app.APIError):
            self.store.add(payload(),digest())
        self.assertEqual(self.store.path.read_text(),'{broken')

    def test_key_change_fails_without_resetting_ledger(self):
        self.store.add(payload(),digest())
        original=self.store.path.read_bytes()
        with self.assertRaises(app.APIError):
            app.VoteStore(self.tmp.name,'different-test-key-at-least-32-characters')
        self.assertEqual(self.store.path.read_bytes(),original)

    def test_missing_secret_rejected(self):
        with self.assertRaises(ValueError):
            app.VoteStore(self.tmp.name,'')

    def test_legacy_migration_backup_and_bandung_scope(self):
        row=dict(payload(),id='legacy-a',created_at='2026-11-03T03:00:00Z',campus='Bandung',is_demo=False)
        foreign=dict(row,id='legacy-b',campus='Jakarta')
        original=json.dumps([foreign,row]).encode()
        self.store.path.write_bytes(original)
        migrated=app.VoteStore(self.tmp.name,KEY)
        backups=list(Path(self.tmp.name).glob('votes.legacy-*.json'))
        self.assertEqual(len(backups),1)
        self.assertEqual(backups[0].read_bytes(),original)
        self.assertEqual(len(migrated.snapshot()),2)
        self.assertFalse(migrated.status(digest())['has_voted'])
        result=app.results(migrated.snapshot(),{})
        self.assertEqual(result['historical_excluded'],1)
        self.assertEqual(result['summary']['total'],1)
        self.assertEqual(result['votes'][0]['index'],1)
        self.assertNotIn('campus',result['groups'])

    def test_privacy_and_no_plain_nim_in_storage(self):
        self.store.add(payload(name='Nama Rahasia',nim=nim()),digest())
        raw=self.store.path.read_text()
        self.assertNotIn(nim(),raw)
        self.assertNotIn('Nama Rahasia',raw)
        public=app.results(self.store.snapshot(),{})
        self.assertNotIn(digest(),json.dumps(public))
        self.assertEqual(set(public['votes'][0]),{'id','alias','created_at','is_demo','index'})

    def test_filter_percentages_and_stale_delete(self):
        first=self.store.add(payload('A',2024),digest(1))
        second=self.store.add(payload('B',2025),digest(2))
        self.store.add(payload('A',2025),digest(3))
        result=app.results(self.store.snapshot(),{'cohort':['2025']})
        self.assertEqual(result['summary']['percent_A'],50)
        self.assertEqual([row['index'] for row in result['votes']],[1,2])
        self.store.delete(0,first['id'])
        with self.assertRaises(app.APIError) as error:
            self.store.delete(1,second['id'])
        self.assertEqual(error.exception.status,409)

    def test_empty_time_filter_and_no_campus_filter(self):
        self.assertEqual(app.results([],{})['summary']['percent_A'],0)
        self.store.add(payload(),digest())
        self.assertEqual(app.results(self.store.snapshot(),{'to':['2000-01-01T00:00:00Z']})['summary']['total'],0)
        for query in ({'campus':['Jakarta']},{'from':['2026-01-02T00:00:00Z'],'to':['2026-01-01T00:00:00Z']}):
            with self.assertRaises(app.APIError):app.results([],query)

    def test_demo_is_explicit_bandung_and_non_reserving(self):
        self.assertEqual(self.store.seed_demo(),120)
        rows=self.store.snapshot()
        self.assertTrue(all(row['campus']=='Bandung' and row['is_demo'] for row in rows))
        self.assertEqual(app.aggregate(rows)['summary']['A'],72)
        self.assertFalse(self.store.status(digest())['has_voted'])
        with self.assertRaises(app.APIError):self.store.seed_demo()

    def test_daily_trend_zero_days(self):
        rows=[dict(payload(),id='a',created_at='2026-10-01T03:00:00Z',is_demo=False),dict(payload('B'),id='b',created_at='2026-10-06T03:00:00Z',is_demo=False)]
        self.assertEqual([r['total'] for r in app.aggregate(rows)['trend']],[1,0,0,0,0,1])


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.logs=patch.object(app.Handler,'log_message').start()
        self.addCleanup(patch.stopall)
        self.start_server()

    def start_server(self):
        self.server=app.make_server(port=0,data_dir=self.tmp.name,serve_frontend=True,hmac_secret=KEY,login_password=PASSWORD,admin_token=ADMIN)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.base='http://127.0.0.1:'+str(self.server.server_port)

    def stop_server(self):
        self.server.shutdown();self.server.server_close();self.thread.join()

    def tearDown(self):
        self.stop_server();self.tmp.cleanup()

    def client(self):
        return build_opener(HTTPCookieProcessor(CookieJar()))

    def call(self,path,method='GET',body=None,client=None,headers=None):
        request=Request(self.base+path,method=method,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json',**(headers or {})})
        try:
            with (client.open(request,timeout=4) if client else urlopen(request,timeout=4)) as response:
                raw=response.read()
                return response.status,json.loads(raw) if raw else {},response.headers
        except HTTPError as error:
            return error.code,json.loads(error.read()),error.headers

    def login(self,number=1,client=None):
        client=client or self.client()
        code,body,headers=self.call('/auth/login','POST',{'nim':nim(number),'password':PASSWORD},client)
        self.assertEqual(code,200)
        return client,body,headers

    def vote(self,client,state,body=None):
        return self.call('/votes','POST',body or payload(),client,{'X-CSRF-Token':state['csrf_token']})

    def test_login_format_password_cookie_and_logout(self):
        self.assertEqual(self.call('/auth/login','POST',{'nim':'1010123','password':PASSWORD})[0],400)
        self.assertEqual(self.call('/auth/login','POST',{'nim':nim(),'password':'wrong'})[0],401)
        client,state,headers=self.login()
        cookie=headers['Set-Cookie']
        self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=Lax',cookie)
        self.assertNotIn(nim(),json.dumps(state))
        self.assertFalse(state['has_voted'])
        self.assertEqual(self.call('/auth/logout','POST',{},client,{'X-CSRF-Token':state['csrf_token']})[0],200)
        self.assertEqual(self.call('/auth/me',client=client)[0],401)

    def test_secure_cookie_when_https_enabled(self):
        self.server.cookie_secure=True
        _,_,headers=self.login()
        self.assertIn('Secure',headers['Set-Cookie'])

    def test_vote_requires_session_and_csrf(self):
        self.assertEqual(self.call('/votes','POST',payload())[0],401)
        client,state,_=self.login()
        self.assertEqual(self.call('/votes','POST',payload(),client)[0],403)
        self.assertEqual(self.vote(client,state)[0],201)

    def test_duplicate_after_logout_and_other_device(self):
        client,state,_=self.login()
        first=self.vote(client,state)[1]
        other,status,_=self.login()
        self.assertTrue(status['has_voted'])
        self.assertEqual(status['voted_at'],first['voted_at'])
        code,duplicate,_=self.vote(other,status)
        self.assertEqual(code,409)
        self.assertEqual(duplicate['voted_at'],first['voted_at'])
        self.assertEqual(duplicate['message'],'terimakasih sudah menggunakan hak pilih anda, hak pilih anda sangat berguna bagi Universitas ini')

    def test_body_nim_cannot_change_session_identity(self):
        client,state,_=self.login(1)
        self.assertEqual(self.vote(client,state,payload(nim=nim(2)))[0],201)
        _,first,_=self.login(1);_,second,_=self.login(2)
        self.assertTrue(first['has_voted']);self.assertFalse(second['has_voted'])

    def test_restart_relogin_retains_time_and_blocks_vote(self):
        client,state,_=self.login()
        first=self.vote(client,state)[1]
        self.stop_server();self.start_server()
        client,state,_=self.login()
        self.assertEqual(state['voted_at'],first['voted_at'])
        self.assertEqual(self.vote(client,state)[0],409)

    def test_admin_delete_does_not_reenable_vote(self):
        client,state,_=self.login()
        vote=self.vote(client,state)[1]['vote']
        route='/votes?index=0&id='+vote['id']
        self.assertEqual(self.call(route,'DELETE',client=client)[0],403)
        self.assertEqual(self.call(route,'DELETE',headers={'X-Admin-Token':ADMIN})[0],200)
        self.assertTrue(self.call('/auth/me',client=client)[1]['has_voted'])
        self.assertEqual(self.vote(client,state)[0],409)

    def test_no_identity_in_public_api_and_logs(self):
        client,state,_=self.login()
        vote=self.vote(client,state,payload(name='Private name'))[1]
        for path in ('/votes','/config','/health'):
            raw=json.dumps(self.call(path)[1])
            self.assertNotIn(nim(),raw);self.assertNotIn(digest(),raw);self.assertNotIn(KEY,raw)
        self.assertEqual(set(vote['vote']),{'id','alias','created_at','is_demo'})
        logged=repr(self.logs.call_args_list)
        self.assertNotIn(nim(),logged);self.assertNotIn(PASSWORD,logged);self.assertNotIn('Private name',logged)

    def test_expired_session_and_cross_origin(self):
        client,state,_=self.login()
        self.assertEqual(self.call('/votes','POST',payload(),client,{'Origin':'https://other.invalid','X-CSRF-Token':state['csrf_token']})[0],403)
        for value in self.server.sessions.entries.values():value['expires']=0
        self.assertEqual(self.call('/auth/me',client=client)[0],401)

    def test_same_origin_port_and_invalid_unicode_csrf(self):
        client,state,_=self.login()
        self.assertEqual(self.call('/votes','POST',payload(),client,{'Origin':self.base,'X-CSRF-Token':'incorrect-é'})[0],403)
        self.assertEqual(self.call('/votes','POST',payload(),client,{'Origin':self.base,'X-CSRF-Token':state['csrf_token']})[0],201)

    def test_parallel_http_sessions_same_nim(self):
        first,one,_=self.login()
        second,two,_=self.login()
        with ThreadPoolExecutor(max_workers=2) as executor:
            a=executor.submit(self.vote,first,one)
            b=executor.submit(self.vote,second,two)
            self.assertEqual(sorted([a.result()[0],b.result()[0]]),[201,409])
        self.assertEqual(len(self.server.store.snapshot()),1)

    def test_demo_tools_require_operator(self):
        self.server.demo_tools=True
        client,_,_=self.login()
        self.assertEqual(self.call('/demo-votes','POST',{},client)[0],403)
        self.assertEqual(self.call('/demo-votes','POST',{},headers={'X-Admin-Token':ADMIN})[0],201)

    def test_sse_add_delete_and_duplicate_no_change(self):
        def event(response):
            while True:
                line=response.readline().decode().strip()
                if line.startswith('data:'):return json.loads(line[5:])
        client,state,_=self.login()
        with urlopen(self.base+'/events',timeout=3) as stream:
            initial=event(stream)
            started=time.monotonic()
            vote=self.vote(client,state)[1]['vote']
            added=event(stream)
            self.assertLess(time.monotonic()-started,2)
            self.assertNotEqual(initial,added)
            self.assertEqual(set(added),{'revision'})
            revision=self.server.store.revision
            self.assertEqual(self.vote(client,state)[0],409)
            self.assertEqual(self.server.store.revision,revision)
            self.call('/votes?index=0&id='+vote['id'],'DELETE',headers={'X-Admin-Token':ADMIN})
            self.assertNotEqual(event(stream),added)

    def test_public_pages_and_login_not_static_password_check(self):
        for path in ('/login.html','/index.html','/dashboard.html','/assets/fonts/Outfit.ttf','/assets/fonts/PlusJakartaSans.ttf'):
            with urlopen(self.base+path,timeout=3) as response:self.assertEqual(response.status,200)
        with urlopen(self.base+'/login.js') as response:self.assertNotIn(b'12345678',response.read())
        self.assertEqual(self.call('/auth/me')[0],401)


if __name__=='__main__':unittest.main()
