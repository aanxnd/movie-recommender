"""Read-only review validation; NEVER submit this partial document to Azure."""
import json
from pathlib import Path
import re
import sys
from copy import deepcopy

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sqlalchemy import URL
from app.native_release import settings
from app.supabase_jwt import _unique_object

API = 'https://movie-recommender-api.nicetree-0929c2a3.canadacentral.azurecontainerapps.io'


def require(condition):
    if not condition: raise ValueError


def _canonical_location(value):
    """Only the pinned region's programmatic name and display name are accepted."""
    require(isinstance(value, str) and value.lower() in {'canadacentral', 'canada central'})
    return 'canadacentral'


def validate(document):
    require(document['name'] == 'movie-recommender-api' and _canonical_location(document['location']) == 'canadacentral')
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


def prepare_native_update(current, existing_secrets, image, env):
    """Pure preparation only. Caller must obtain final approval before PATCH/start."""
    resource = ('/subscriptions/b118c1af-4183-49d6-bb49-1b531355fa3f/resourceGroups/'
                'movie-recommender-rg/providers/Microsoft.App/containerApps/movie-recommender-api')
    require(current['id'].lower() == resource.lower())
    location = _canonical_location(current['location'])
    p = current['properties']; c = p['configuration']; t = deepcopy(p['template'])
    expected_environment = resource.rsplit('/containerApps/',1)[0] + '/managedEnvironments/managedEnvironment-movierecommende-9747'
    require((p.get('environmentId') or p.get('managedEnvironmentId','')).lower() == expected_environment.lower())
    require(p['runningStatus'] == 'Stopped' and p['provisioningState'] == 'Succeeded')
    require(c['activeRevisionsMode'] == 'Single' and c['ingress']['fqdn'] == API.removeprefix('https://'))
    require(c['ingress']['external'] is True and c['ingress']['allowInsecure'] is False and c['ingress']['targetPort'] == 8000)
    require(len(t['containers']) == 1 and not t.get('initContainers') and not t.get('volumes'))
    container = t['containers'][0]
    require(not container.get('volumeMounts') and container['resources']['cpu'] == 1 and container['resources']['memory'] == '2Gi')
    # Reported by GET but readOnly in the PATCH schema; storage stays platform-managed.
    container['resources'].pop('ephemeralStorage', None)
    scale = t['scale']; rules = scale['rules']
    require(scale['minReplicas'] == 0 and scale['maxReplicas'] in {1,3} and len(rules) == 1)
    require(rules[0]['name'] == 'http-scaler' and rules[0]['http']['metadata'] == {'concurrentRequests':'10'})
    require(set(rules[0]) <= {'name','http'} and not rules[0]['http'].get('auth'))
    raw = env['MOVELLE_NATIVE_TARGETS_JSON']; require(len(raw) <= 8192)
    targets = json.loads(raw,object_pairs_hook=_unique_object)
    require(targets['api_origin'] == API and targets['supabase_url'] == 'https://jsbulnrcxtvslvvxjizq.supabase.co')
    require(targets['database_host'] == 'ep-falling-pine-b45yu0ao.c-6.us-east-2.aws.neon.tech' and targets['database_name'] == 'neondb')
    values = {'APP_ENV':'production','PORT':'8000','MOVELLE_NATIVE_MODE':'native-release',
              'MOVELLE_NATIVE_PREPARED_DIR':'/backend/data/reference/ml-32m-v1',
              'MOVELLE_NATIVE_TARGETS_JSON':raw,'CORS_ALLOWED_ORIGINS':env['CORS_ALLOWED_ORIGINS']}
    settings(dict(values,MOVELLE_NATIVE_DATABASE_URL=env['MOVELLE_NATIVE_DATABASE_URL'],
                  MOVELLE_NATIVE_PUBLISHABLE_KEY=env['MOVELLE_NATIVE_PUBLISHABLE_KEY']),targets)
    container['image'] = image
    for key in ['command','args']: container.pop(key,None)
    t.pop('revisionSuffix',None)
    container['env'] = [dict(name=k,value=v) for k,v in values.items()] + [
        {'name':'MOVELLE_NATIVE_DATABASE_URL','secretRef':'movelle-native-database'},
        {'name':'MOVELLE_NATIVE_PUBLISHABLE_KEY','secretRef':'movelle-native-publishable-key'}]
    container['probes'] = [{'type':kind,'httpGet':{'path':'/health','port':8000},'periodSeconds':period,
                           'timeoutSeconds':2,'failureThreshold':failures} for kind,period,failures in [
                               ('Startup',10,30),('Liveness',60,3),('Readiness',30,3)]]
    scale['maxReplicas'] = 1
    # Existing validator checks the exact approved fields; unchanged platform defaults survive.
    selected = deepcopy(t)
    selected['scale'] = {k:scale[k] for k in ['minReplicas','maxReplicas','rules']}
    selected['containers'][0]['resources'] = {'cpu':1,'memory':'2Gi'}
    validate({'name':current['name'],'location':location,'properties':{'configuration':c,'template':selected}})
    names = [s['name'] for s in existing_secrets]
    require(len(set(names)) == len(names) and set(names) == {s['name'] for s in c.get('secrets',[])})
    for secret in existing_secrets:
        require(set(secret) <= {'name','value','identity','keyVaultUrl'} and (secret.get('value') or secret.get('keyVaultUrl')))
    merged = {s['name']:deepcopy(s) for s in existing_secrets}
    for name,value in [('movelle-native-database',env['MOVELLE_NATIVE_DATABASE_URL']),
                       ('movelle-native-publishable-key',env['MOVELLE_NATIVE_PUBLISHABLE_KEY'])]:
        merged[name] = {'name':name,'value':value}
    # JSON Merge Patch changes only the native template and merged secret list.
    return {'location':location,'properties':{'configuration':{'secrets':list(merged.values())},'template':t}}


if __name__ == '__main__':
    try:
        if len(sys.argv) != 2: raise ValueError
        with Path(sys.argv[1]).open(encoding='utf-8') as stream: raw = stream.read(65537)
        if len(raw) > 65536: raise ValueError
        validate(json.loads(raw, object_pairs_hook=_unique_object))
        print('Review fields validated; billing, scope, secrets and deployment NOT approved')
    except Exception:
        raise SystemExit('Azure review configuration refused') from None
