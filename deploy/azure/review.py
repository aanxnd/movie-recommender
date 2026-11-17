"""Read-only review validation; NEVER submit this partial document to Azure."""
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sqlalchemy import URL
from app.native_release import settings
from app.supabase_jwt import _unique_object

API = 'https://movie-recommender-api.nicetree-0929c2a3.canadacentral.azurecontainerapps.io'


def require(condition):
    if not condition: raise ValueError


def validate(document):
    require(document['name'] == 'movie-recommender-api' and document['location'] == 'canadacentral')
    config, template = (document['properties'][key] for key in ['configuration', 'template'])
    require(config['activeRevisionsMode'] == 'Single')
    ingress = config['ingress']
    require(ingress['external'] is True and ingress['targetPort'] == 8000 and ingress['allowInsecure'] is False)
    require(template['scale'] == {'minReplicas': 0, 'maxReplicas': 1, 'rules': [
        {'name': 'http-scaler', 'http': {'metadata': {'concurrentRequests': '10'}}}]})
    require(len(template['containers']) == 1 and not template.get('initContainers') and not template.get('volumes'))
    container = template['containers'][0]
    require(re.fullmatch(r'[a-z][a-z0-9-]{0,62}', container['name']))
    require(re.fullmatch(r'ghcr.io/aanxnd/movie-recommender@sha256:[a-f0-9]{64}', container['image']))
    require(container['resources'] == {'cpu': 1, 'memory': '2Gi'})
    require(not container.get('command') and not container.get('args'))  # Use reviewed image CMD.
    rows = container['env']; env = {row['name']: row.get('value') for row in rows}
    require(len(env) == len(rows) and set(env) == {'APP_ENV', 'PORT', 'MOVELLE_NATIVE_MODE',
        'MOVELLE_NATIVE_PREPARED_DIR', 'MOVELLE_NATIVE_TARGETS_JSON', 'CORS_ALLOWED_ORIGINS',
        'MOVELLE_NATIVE_DATABASE_URL', 'MOVELLE_NATIVE_PUBLISHABLE_KEY'})
    require(env['PORT'] == '8000' and env['MOVELLE_NATIVE_PREPARED_DIR'] == '/backend/data/reference/ml-32m-v1')
    for name, reference in [('MOVELLE_NATIVE_DATABASE_URL', 'movelle-native-database'),
                            ('MOVELLE_NATIVE_PUBLISHABLE_KEY', 'movelle-native-publishable-key')]:
        require(next(row for row in rows if row['name'] == name) == {'name': name, 'secretRef': reference})
    raw = env['MOVELLE_NATIVE_TARGETS_JSON']; require(isinstance(raw, str) and len(raw) <= 8192)
    targets = json.loads(raw, object_pairs_hook=_unique_object)
    require(targets['api_origin'] == API)
    # Reuse production target validation with FICTIONAL credentials only. No IO.
    env['MOVELLE_NATIVE_DATABASE_URL'] = URL.create('postgresql', username='movelle_native',
        password='offline-only', host=targets['database_host'], database=targets['database_name'],
        query={'sslmode': 'verify-full', 'sslrootcert': 'system', 'channel_binding': 'require'}).render_as_string(hide_password=False)
    env['MOVELLE_NATIVE_PUBLISHABLE_KEY'] = 'sb_publishable_offline'
    settings(env, targets)
    probes = container['probes']; require(len(probes) == 3)
    require({p['type'] for p in probes} == {'Startup', 'Liveness', 'Readiness'})
    for p in probes:
        require(p['httpGet'] == {'path': '/health', 'port': 8000})
        require(10 <= p['periodSeconds'] <= 60 and p['timeoutSeconds'] == 2)
        require(p['failureThreshold'] == (30 if p['type'] == 'Startup' else 3))


if __name__ == '__main__':
    try:
        if len(sys.argv) != 2: raise ValueError
        with Path(sys.argv[1]).open(encoding='utf-8') as stream: raw = stream.read(65537)
        if len(raw) > 65536: raise ValueError
        validate(json.loads(raw, object_pairs_hook=_unique_object))
        print('Review fields validated; billing, scope, secrets and deployment NOT approved')
    except Exception:
        raise SystemExit('Azure review configuration refused') from None
