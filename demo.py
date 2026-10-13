#!/usr/bin/env python3
"""Run the pinned Astronomy Shop stack in an isolated Compose project."""

import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / '.runtime'
UPSTREAM = RUNTIME / 'opentelemetry-demo'
REVISION = '9bfe486ff48ee8a6ea942be74171342cb71a9327'
PROJECT = 'greptime-demo'
CONFIG = RUNTIME / 'compose.json'


def greptime_base_url(endpoint):
    """Derive the GreptimeDB HTTP base URL from an OTLP endpoint like http://host:4000/v1/otlp."""
    for suffix in ('/v1/otlp', '/v1/otlp/'):
        if endpoint.endswith(suffix):
            return endpoint[: -len(suffix)]
    return endpoint.rstrip('/') or 'http://localhost:4000'


def yaml_quote(value):
    return "'" + value.replace("'", "''") + "'"


def render_prometheus_config():
    """Render .runtime/prometheus.yml with the external remote_write URL and Basic Auth."""
    base_url = greptime_base_url(os.environ.get('GREPTIMEDB_ENDPOINT', ''))
    username = os.environ.get('GREPTIMEDB_USERNAME', '')
    password = os.environ.get('GREPTIMEDB_PASSWORD', '')
    remote_write = 'remote_write:\n  - url: ' + yaml_quote(base_url.rstrip('/') + '/v1/prometheus/write?db=public')
    if username or password:
        remote_write += '\n    basic_auth:\n      username: ' + yaml_quote(username) + '\n      password: ' + yaml_quote(password)
    template = (ROOT / 'prometheus.yml').read_text().replace('__REMOTE_WRITE__', remote_write)
    (RUNTIME / 'prometheus.yml').write_text(template.rstrip() + '\n')
    return base_url


def render():
    RUNTIME.mkdir(exist_ok=True)
    if not UPSTREAM.exists():
        subprocess.run(['git', 'clone', 'https://github.com/open-telemetry/opentelemetry-demo.git', str(UPSTREAM)], check=True)
        subprocess.run(['git', '-C', str(UPSTREAM), 'checkout', '--detach', REVISION], check=True)
    revision = subprocess.check_output(['git', '-C', str(UPSTREAM), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != REVISION:
        raise RuntimeError(f'{UPSTREAM} is at {revision}; expected {REVISION}. Existing checkout was not changed.')
    base_url = render_prometheus_config()
    env = dict(
        os.environ,
        OTEL_COLLECTOR_CONFIG_EXTRAS=str(ROOT / 'otelcol-config-greptime.yml'),
        PUBLIC_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT='http://localhost:18080/otlp-http/v1/traces',
        GREPTIMEDB_HTTP=base_url,
        GREPTIMEDB_PROMETHEUS_CONFIG=str(RUNTIME / 'prometheus.yml'),
    )
    command = ['docker', 'compose', '-f', str(UPSTREAM / 'compose.yaml'), '-f', str(ROOT / 'compose.greptime.yaml'), 'config', '--format', 'json']
    config = json.loads(subprocess.check_output(command, cwd=UPSTREAM, env=env, text=True))
    images = json.loads((ROOT / 'images.lock.json').read_text())
    config['name'] = PROJECT
    config['networks']['default']['name'] = PROJECT
    ports = {'frontend-proxy': {8080: 18080, 10000: 18081}}
    for name, service in config['services'].items():
        service.pop('container_name', None)
        service['image'] = images[name]
        for port in service.get('ports', []):
            port['host_ip'] = '127.0.0.1'
            if port['target'] in ports.get(name, {}):
                port['published'] = str(ports[name][port['target']])
        for volume in service.get('volumes', []):
            if volume['type'] == 'bind':
                source = Path(volume['source'])
                prefix = UPSTREAM / 'greptime'
                if source.is_relative_to(prefix):
                    volume['source'] = str(ROOT / source.relative_to(prefix))
                # Docker Desktop on macOS cannot apply rslave propagation to the
                # host root, which node-exporter mounts as /:/host:ro,rslave.
                if platform.system() == 'Darwin':
                    volume.get('bind', {}).pop('propagation', None)
    for name, volume in config.get('volumes', {}).items():
        volume['name'] = f'{PROJECT}_{name}'
    CONFIG.write_text(json.dumps(config, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['up', 'down', 'ps', 'logs', 'config'])
    parser.add_argument('services', nargs='*', help='Optional services for logs')
    args = parser.parse_args()
    if args.action in ('up', 'config'):
        render()
    elif not CONFIG.exists():
        raise RuntimeError('Run demo.py up first')
    if args.action == 'config':
        print(CONFIG)
        return
    command = ['docker', 'compose', '-p', PROJECT, '-f', str(CONFIG)]
    if args.action == 'up':
        command += ['up', '-d', '--no-build', '--wait', '--wait-timeout', '180']
    elif args.action == 'logs':
        command += ['logs', '--tail', '100', *args.services]
    else:
        command += [args.action]
    subprocess.run(command, check=True)
    if args.action == 'up':
        print('Shop: http://localhost:18080')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
