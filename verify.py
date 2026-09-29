#!/usr/bin/env python3
"""Validate a checkout and telemetry ingestion into the external GreptimeDB."""

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


def base_url_from_otlp(endpoint):
    """Derive the GreptimeDB HTTP base URL from an OTLP endpoint like http://host:4000/v1/otlp."""
    for suffix in ('/v1/otlp', '/v1/otlp/'):
        if endpoint.endswith(suffix):
            return endpoint[: -len(suffix)]
    return endpoint.rstrip('/') or 'http://localhost:4000'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--greptime', default=base_url_from_otlp(os.environ.get('GREPTIMEDB_ENDPOINT', 'http://localhost:4000')))
    parser.add_argument('--username', default=os.environ.get('GREPTIMEDB_USERNAME'))
    parser.add_argument('--password', default=os.environ.get('GREPTIMEDB_PASSWORD'))
    parser.add_argument('--shop', default='http://localhost:18080')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    http = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def auth_header():
        if args.username is not None or args.password is not None:
            token = base64.b64encode(f'{args.username or ""}:{args.password or ""}'.encode()).decode()
            return {'Authorization': f'Basic {token}'}
        return {}

    def request(url, data=None, headers=None):
        headers = dict(headers or {})
        if data is not None:
            headers['Content-Type'] = 'application/json'
        payload = json.dumps(data).encode() if data is not None else None
        try:
            with http.open(urllib.request.Request(url, payload, headers), timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            raise RuntimeError(f'{url}: HTTP {error.code}: {error.read().decode()}') from error

    def sql(statement):
        url = args.greptime + '/v1/sql?' + urllib.parse.urlencode({'sql': statement})
        result = json.loads(request(url, headers=auth_header()))
        if result.get('error'):
            raise RuntimeError(result['error'])
        return result['output'][0]['records']['rows']

    def literal(value):
        return "'" + value.replace("'", "''") + "'"

    request(args.shop)
    print('PASS shop HTTP')
    for endpoint in ('/api/products/0PUK6V6EV0', '/api/currency', '/api/recommendations?productIds=0PUK6V6EV0', '/api/data?contextKeys=assembly'):
        result = json.loads(request(args.shop + endpoint))
        if not result:
            raise RuntimeError(f'Empty response from {endpoint}')
        print('PASS shop', endpoint)

    checkout_trace = uuid.uuid4().hex
    trace_headers = {'traceparent': f'00-{checkout_trace}-{uuid.uuid4().hex[:16]}-01'}
    person = json.loads((root / '.runtime/opentelemetry-demo/src/load-generator/people.json').read_text())[0]
    person['userId'] = 'verify-' + checkout_trace
    request(args.shop + '/api/cart', {'userId': person['userId'], 'item': {'productId': '0PUK6V6EV0', 'quantity': 1}}, trace_headers)
    order = json.loads(request(args.shop + '/api/checkout', person, trace_headers))
    if not order.get('orderId'):
        raise RuntimeError(f'Checkout did not create an order: {order}')
    deadline = time.monotonic() + 30
    while True:
        quote_spans = sql(f'''SELECT "span_attributes.http.request.body.size", "span_attributes.http.response.body.size"
            FROM opentelemetry_traces WHERE trace_id = {literal(checkout_trace)}
            AND service_name = 'quote' AND span_name = 'POST /getquote' ''')
        if quote_spans:
            break
        if time.monotonic() >= deadline:
            raise RuntimeError('Checkout succeeded but its quote server span was not ingested')
        time.sleep(1)
    if any(not isinstance(size, int) or size <= 0 or response_size is not None for size, response_size in quote_spans):
        raise RuntimeError(f'Quote HTTP body sizes were not normalized correctly: {quote_spans}')
    print(f'PASS checkout and quote span ingestion: {checkout_trace}')

    namespace = '\"resource_attributes.service.namespace\" = \'opentelemetry-demo\''
    services = [row[0] for row in sql(f'SELECT DISTINCT service_name FROM opentelemetry_traces WHERE {namespace}')]
    if not services:
        raise RuntimeError('No Astronomy Shop services have emitted traces')
    print(f'PASS services emitting traces: {sorted(services)}')

    log_namespace = '''json_get_string(resource_attributes, '["service.namespace"]') = 'opentelemetry-demo' '''.strip()
    for name, statement in {
        'server spans': f'SELECT COUNT(*) FROM opentelemetry_traces WHERE {namespace} AND span_kind = \'SPAN_KIND_SERVER\' AND "timestamp" > now() - INTERVAL \'5 minutes\'',
        'application logs': f'SELECT COUNT(*) FROM opentelemetry_logs WHERE {log_namespace} AND "timestamp" > now() - INTERVAL \'5 minutes\'',
    }.items():
        count = sql(statement)[0][0]
        if count == 0:
            raise RuntimeError(f'No recent {name}')
        print(f'PASS {name}: {count} rows')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (RuntimeError, urllib.error.URLError, TimeoutError) as error:
        print(f'FAIL {error}', file=sys.stderr)
        sys.exit(1)
