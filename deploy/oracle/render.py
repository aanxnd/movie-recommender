"""Offline generation into a NEW directory. Never invokes Docker, TLS or cloud APIs."""
import argparse
import ipaddress
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


def host(origin):
    parsed = urlsplit(origin)
    name = parsed.hostname
    if (not isinstance(origin, str) or not name or origin != 'https://' + name
            or not re.fullmatch(r'[a-z0-9]+(?:[.-][a-z0-9]+)*', name) or name == 'localhost'):
        raise ValueError
    try:
        address = ipaddress.ip_address(name)
    except ValueError:
        if '.' not in name: raise ValueError
    else:
        if not address.is_global: raise ValueError
    return name


def render(targets):
    if (targets.get('approved') is not True or targets['frontend_origin'] == targets['api_origin']
            or not re.fullmatch(r'https://[a-z0-9]{20}\.supabase\.co', targets['supabase_url'])
            or not re.fullmatch(r'ep-[a-z0-9-]+(?:\.[a-z0-9-]+)+\.neon\.tech', targets['database_host'])
            or not re.fullmatch(r'[a-z][a-z0-9_]{0,62}', targets['database_name'])):
        raise ValueError
    host(targets['frontend_origin'])
    api = host(targets['api_origin'])
    try: ipaddress.ip_address(api); literal = True
    except ValueError: literal = False
    # RFC6066 excludes IP literals from SNI. Only the approved IP certificate is
    # served by the default socket; nonempty SNI and wrong HTTP Host never proxy.
    substitutions = {
        'API_HOST': api,
        'TLS_DEFAULT': '' if literal else
            'server { listen 8443 ssl default_server; server_name _; ssl_reject_handshake on; return 444; }',
        'TLS_LISTEN': '8443 ssl default_server' if literal else '8443 ssl',
        'SNI_GUARD': "if ($ssl_server_name != '') { return 444; }" if literal else '',
    }
    template = Path(__file__).with_name('nginx.conf.in').read_text()
    for key, value in substitutions.items(): template = template.replace('@@' + key + '@@', value)
    return template


def prepare(manifest, output):
    from app.supabase_jwt import _unique_object
    with Path(manifest).open(encoding='utf-8') as stream:
        raw = stream.read(8193)
    if len(raw) > 8192: raise ValueError
    targets = json.loads(raw, object_pairs_hook=_unique_object)
    proxy = render(targets)
    output = Path(output)
    output.mkdir()  # Never overwrite/recurse into existing operator resources.
    (output / 'targets.json').write_text(json.dumps(targets), encoding='utf-8')
    (output / 'nginx.conf').write_text(proxy, encoding='utf-8')


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--targets', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try: prepare(args.targets, args.output)
    except Exception: raise SystemExit('Oracle configuration preparation refused') from None
