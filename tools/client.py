"""Local acceptance-test client. Runtime credentials never printed."""
import json
import secrets
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPCookieProcessor
from settings import runtime_config


class Client:
    def __init__(self, base):
        self.base = base.rstrip('/')
        self.config = runtime_config()
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))
        self.csrf = ''

    def call(self, path, method='GET', body=None, admin=False, expected=200):
        headers = {'Content-Type':'application/json'}
        if self.csrf:
            headers['X-CSRF-Token'] = self.csrf
        if admin:
            headers['X-Admin-Token'] = self.config.get('ADMIN_TOKEN','')
        req = Request(self.base+path,method=method,data=None if body is None else json.dumps(body).encode(),headers=headers)
        try:
            with self.opener.open(req,timeout=6) as response:
                status,data=response.status,json.load(response)
        except HTTPError as error:
            status,data=error.code,json.load(error)
        if status != expected:
            # Never print request bodies, NIM, cookie headers, or configured keys.
            raise RuntimeError(f'Unexpected HTTP {status} at {path.split("?")[0]} (expected {expected})')
        return data

    def login(self, nim):
        state=self.call('/auth/login','POST',{'nim':nim,'password':self.config.get('LOGIN_PASSWORD','12345678')})
        self.csrf=state['csrf_token']
        return state

    def fresh_test_identity(self):
        for _ in range(10):
            value='1010'+f'{secrets.randbelow(100000000):08d}'
            state=self.login(value)
            if not state['has_voted']:
                return value
        raise RuntimeError('Could not find an unused synthetic test identity')
