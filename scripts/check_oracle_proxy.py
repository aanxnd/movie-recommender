"""Disposable loopback TLS fixture. No production certificate, API or credential."""
from datetime import datetime, timedelta, timezone
import http.client
import ipaddress
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deploy.oracle.render import render

IMAGE = 'nginx:stable-alpine@sha256:901e593c95dc85f5a729f5765516321366ef4ac401821431d408897e95287d0a'


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True, stderr=subprocess.PIPE).strip()


def check(api_host='api.example'):
    name, created = 'movelle-oracle-check-' + uuid4().hex, False
    with tempfile.TemporaryDirectory(prefix='movelle-oracle-check-') as directory:
        root = Path(directory)
        assert root.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
        tls = root / 'tls' / 'current'; tls.mkdir(parents=True)
        acme = root / 'acme'; acme.mkdir()
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, api_host)])
        try: san = x509.IPAddress(ipaddress.ip_address(api_host))
        except ValueError: san = x509.DNSName(api_host)
        now = datetime.now(timezone.utc)
        cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(hours=1))
            .add_extension(x509.SubjectAlternativeName([san]), False)
            .sign(key, hashes.SHA256()))
        (tls / 'fullchain.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        (tls / 'privkey.pem').write_bytes(key.private_bytes(serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        # Fictional, ephemeral key only. Production requires restrictive host ownership.
        (tls / 'privkey.pem').chmod(0o644)
        targets = dict(approved=True, frontend_origin='https://frontend.example', api_origin='https://' + api_host,
            supabase_url='https://'+'a'*20+'.supabase.co', database_host='ep-fixture.ca.neon.tech', database_name='fixture')
        (root / 'nginx.conf').write_text(render(targets))
        for filename in ['native_database_url', 'native_publishable_key', 'targets.json']:
            (root / filename).write_text('offline-fixture')
        env = dict(os.environ)
        for suffix in ['CONFIG', 'REFERENCE', 'SECRETS', 'TLS', 'ACME']:
            env['MOVELLE_ORACLE_' + suffix] = str(root)
        env.update(MOVELLE_ORACLE_IMAGE='sha256:'+'0'*64,
                   MOVELLE_ORACLE_FRONTEND_ORIGIN=targets['frontend_origin'])
        parsed = json.loads(subprocess.check_output(['docker', 'compose', '-f',
            str(Path(__file__).resolve().parents[1]/'deploy/oracle/compose.yaml'),
            'config', '--format', 'json'], env=env, text=True))
        api, proxy = (parsed['services'][key] for key in ['api', 'proxy'])
        assert not api.get('ports') and api['read_only'] and proxy['read_only']
        assert sorted(str(p['published']) for p in proxy['ports']) == ['443', '80']
        assert api['platform'] == proxy['platform'] == 'linux/arm64'
        args = ['create', '--name', name, '--user', '101:101', '--read-only', '--cap-drop=ALL',
            '--security-opt=no-new-privileges', '--pids-limit=64', '--memory=128m', '--cpus=.25',
            '--tmpfs', '/tmp:rw,noexec,nosuid,size=16m,uid=101,gid=101,mode=0700',
            '--add-host', 'api:127.0.0.1', '-p', '127.0.0.1::8443', '-p', '127.0.0.1::8080']
        for source, target in [(root/'nginx.conf', '/etc/nginx/nginx.conf'), (root/'tls', '/tls'), (acme, '/var/www/acme')]:
            args += ['--mount', f'type=bind,source={source},target={target},readonly']
        try:
            docker(*args, '--entrypoint', 'nginx', IMAGE, '-g', 'daemon off;'); created = True
            docker('start', name)
            port = int(docker('port', name, '8443/tcp').rsplit(':', 1)[1])
            context = ssl.create_default_context(cafile=str(tls/'fullchain.pem'))
            def request(host=api_host, sni=api_host, body=b'', tls_context=context):
                with socket.create_connection(('127.0.0.1', port), timeout=2) as tcp:
                    with tls_context.wrap_socket(tcp, server_hostname=sni) as stream:
                        stream.sendall(f"POST /fixture HTTP/1.1\r\nHost: {host}\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()+body)
                        return stream.recv(65536)
            deadline = time.monotonic()+15
            while True:
                try: response = request(); break
                except (OSError, ssl.SSLError):
                    if time.monotonic() > deadline: raise
                    time.sleep(.2)
            assert b'502 Bad Gateway' in response  # No mock upstream; never a real API.
            assert request(host='evil.example') == b''
            if isinstance(san, x509.IPAddress):
                # Negative probe: trust only our fixture CA but let the server
                # demonstrate HTTP rejection of unexpected SNI after handshake.
                probe = ssl.create_default_context(cafile=str(tls/'fullchain.pem'))
                probe.check_hostname = False
                assert request(sni='evil.example', tls_context=probe) == b''
            else:
                try: request(sni='evil.example')
                except ssl.SSLError: pass
                else: raise AssertionError('Unknown TLS name accepted')
            assert b'413' in request(body=b'x'*17000)
            plain = http.client.HTTPConnection('127.0.0.1', int(docker('port', name, '8080/tcp').rsplit(':', 1)[1]))
            plain.request('GET', '/secret?code=FIXTURE_MARKER', headers={'Host':api_host})
            response = plain.getresponse()
            assert response.status == 308 and response.getheader('Location') == 'https://' + api_host + '/'
            plain.close()
            logs = subprocess.run(['docker', 'logs', name], capture_output=True, text=True, check=True)
            assert 'FIXTURE_MARKER' not in logs.stdout + logs.stderr
            print('Loopback TLS, wrong-host/SNI, body bound, redirect and log isolation passed:', api_host)
        finally:
            if created: docker('rm', '--force', name)


if __name__ == '__main__':
    check()
    check('8.8.8.8')  # IP SAN/no-SNI fixture; all sockets still connect to loopback.
