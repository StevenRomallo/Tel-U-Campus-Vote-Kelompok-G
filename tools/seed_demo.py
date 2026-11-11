"""Explicitly seed demo data into an EMPTY store via the running API."""
import argparse
import json
from client import Client

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8097')
    parser.add_argument('--confirm', action='store_true', help='Required to add 120 fictional records')
    args = parser.parse_args()
    if not args.confirm:
        parser.error('Use --confirm to explicitly authorize fictional demo data')
    result=Client(args.url).call('/demo-votes','POST',{},admin=True,expected=201)
    print(result['message'])
