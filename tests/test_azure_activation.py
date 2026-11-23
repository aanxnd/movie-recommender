"""Fictional Azure snapshots only. Never calls Azure or any application database."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from sqlalchemy import URL

from deploy.azure import review


@pytest.fixture
def inputs():
    resource='/subscriptions/b118c1af-4183-49d6-bb49-1b531355fa3f/resourceGroups/movie-recommender-rg/providers/Microsoft.App/containerApps/movie-recommender-api'
    current=json.loads(Path('deploy/azure/containerapp.review.json').read_text())
    current['id']=resource;p=current['properties'];p.update(runningStatus='Stopped',provisioningState='Succeeded',environmentId=resource.rsplit('/containerApps/',1)[0]+'/managedEnvironments/managedEnvironment-movierecommende-9747')
    current['identity']={'type':'SystemAssigned','principalId':'fictional'}
    p['configuration']['secrets']=[{'name':'old-secret'}];p['configuration']['registries']=[{'server':'existing.invalid'}]
    p['configuration']['ingress']['fqdn']=review.API.removeprefix('https://')
    p['template']['scale']['maxReplicas']=3;p['template']['scale']['cooldownPeriod']=300
    container=p['template']['containers'][0];container['name']='existing-container';container['image']='existing-legacy-image'
    container['command']=['python','-m','app.runtime'];container['env']=[{'name':'LEGACY','secretRef':'old-secret'}]
    targets={'approved':True,'frontend_origin':'https://fixture.example','api_origin':review.API,
             'supabase_url':'https://jsbulnrcxtvslvvxjizq.supabase.co',
             'database_host':'ep-falling-pine-b45yu0ao.c-6.us-east-2.aws.neon.tech','database_name':'neondb'}
    url=URL.create('postgresql',username='movelle_native',password='Fictional-only',host=targets['database_host'],database='neondb',query={'sslmode':'verify-full','sslrootcert':'system','channel_binding':'require'})
    env={'MOVELLE_NATIVE_TARGETS_JSON':json.dumps(targets),'CORS_ALLOWED_ORIGINS':targets['frontend_origin'],
         'MOVELLE_NATIVE_DATABASE_URL':url.render_as_string(hide_password=False),'MOVELLE_NATIVE_PUBLISHABLE_KEY':'sb_publishable_fictional'}
    return current,[{'name':'old-secret','value':'Fictional-old-only'}],'ghcr.io/aanxnd/movie-recommender@sha256:'+'a'*64,env


def test_only_native_template_and_merged_secrets_change(inputs):
    before=deepcopy(inputs);current,secrets,image,env=inputs
    patch=review.prepare_native_update(*inputs)
    assert inputs==before
    assert set(patch)=={'location','properties'} and set(patch['properties'])=={'configuration','template'}
    assert set(patch['properties']['configuration'])=={'secrets'}
    assert patch['properties']['configuration']['secrets'][0]==secrets[0]
    template=patch['properties']['template'];c=template['containers'][0]
    assert c['name']=='existing-container' and c['image']==image and 'command' not in c
    assert template['scale']['maxReplicas']==1 and template['scale']['cooldownPeriod']==300
    assert all('secretRef' in row for row in c['env'] if row['name'] in {'MOVELLE_NATIVE_DATABASE_URL','MOVELLE_NATIVE_PUBLISHABLE_KEY'})
    assert 'Fictional-only' not in json.dumps(template) and 'Fictional-old-only' not in json.dumps(template)
    assert all(row['name']!='LEGACY' for row in c['env'])


@pytest.mark.parametrize('attack',['subscription','environment','running','provisioning','fqdn','http','replicas',
    'memory','sidecar','volume','scaler','image','secrets','duplicate-secret','approval','supabase','database','role','tls','origin'])
def test_drift_or_unsafe_input_prevents_payload_creation(inputs,attack):
    current,secrets,image,env=inputs;p=current['properties'];t=p['template'];targets=json.loads(env['MOVELLE_NATIVE_TARGETS_JSON'])
    if attack=='subscription':current['id']=current['id'].replace('b118c1af','00000000')
    elif attack=='environment':p['environmentId']='/wrong'
    elif attack=='running':p['runningStatus']='Running'
    elif attack=='provisioning':p['provisioningState']='Failed'
    elif attack=='fqdn':p['configuration']['ingress']['fqdn']='other.invalid'
    elif attack=='http':p['configuration']['ingress']['allowInsecure']=True
    elif attack=='replicas':t['scale']['minReplicas']=1
    elif attack=='memory':t['containers'][0]['resources']['memory']='4Gi'
    elif attack=='sidecar':t['containers'].append(deepcopy(t['containers'][0]))
    elif attack=='volume':t['volumes']=[{'name':'extra'}]
    elif attack=='scaler':t['scale']['rules'][0]['http']['metadata']['concurrentRequests']='100'
    elif attack=='image':image='other.invalid:latest'
    elif attack=='secrets':secrets[0].pop('value')
    elif attack=='duplicate-secret':secrets.append(deepcopy(secrets[0]))
    elif attack=='approval':targets['approved']=False
    elif attack=='supabase':targets['supabase_url']='https://abcdefghijklmnopqrst.supabase.co'
    elif attack=='database':targets['database_name']='other'
    elif attack=='role':env['MOVELLE_NATIVE_DATABASE_URL']=env['MOVELLE_NATIVE_DATABASE_URL'].replace('movelle_native','neondb_owner')
    elif attack=='tls':env['MOVELLE_NATIVE_DATABASE_URL']=env['MOVELLE_NATIVE_DATABASE_URL'].replace('verify-full','require')
    elif attack=='origin':env['CORS_ALLOWED_ORIGINS']='*'
    env['MOVELLE_NATIVE_TARGETS_JSON']=json.dumps(targets)
    with pytest.raises(Exception):review.prepare_native_update(current,secrets,image,env)


def test_workflow_requires_explicit_activation_and_retains_protection_contract():
    raw=Path('.github/workflows/publish-image.yml').read_text()
    assert raw.count("if: ${{ github.ref == 'refs/heads/main' && inputs.confirm_native_activation == true }}")==2
    assert 'required: true' in raw and 'default: false' in raw
    for control in ['environment: production','cancel-in-progress: false','Reject stale release',
        "github.ref == 'refs/heads/main'",'needs: verify','needs: publish','app.native_preflight',
        'linux/amd64','sbom: true','provenance: true']:
        assert control in raw
    assert '--body' in raw and "'@'+str(path)" in raw and 'capture_output=True' in raw
    assert 'migrate' not in raw and 'neon_superuser' not in raw
    assert raw.index("+'/deactivate'") < raw.index("request('patch',body=patch)") < raw.index("request('post','/start')")
    assert "check(not any(r['properties']['active']" in raw and "containers[0]['image'] == old_image" in raw
