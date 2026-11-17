import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from deploy.azure import review
from test_native_release import config


@pytest.fixture
def document():
    value = json.loads(Path('deploy/azure/containerapp.review.json').read_text())
    _, targets = config(); targets['api_origin'] = review.API
    container = value['properties']['template']['containers'][0]
    container['name'] = 'fixture'
    container['image'] = 'ghcr.io/aanxnd/movie-recommender@sha256:' + 'a' * 64
    for row in container['env']:
        if row['name'] == 'MOVELLE_NATIVE_TARGETS_JSON': row['value'] = json.dumps(targets)
        if row['name'] == 'CORS_ALLOWED_ORIGINS': row['value'] = targets['frontend_origin']
    return value


def test_review_only_accepts_the_pinned_native_configuration(document):
    before = copy.deepcopy(document)
    review.validate(document)
    assert document == before
    with pytest.raises(Exception): review.validate(json.loads(Path('deploy/azure/containerapp.review.json').read_text()))


@pytest.mark.parametrize('attack', ['app', 'region', 'revision', 'http', 'replicas', 'scaler',
    'image', 'command', 'sidecar', 'memory', 'secret', 'duplicate', 'origin', 'probe', 'storage'])
def test_bad_scope_cost_or_security_inputs_are_refused(document, attack):
    properties = document['properties']; template = properties['template']; container = template['containers'][0]
    if attack == 'app': document['name'] = 'other'
    elif attack == 'region': document['location'] = 'other'
    elif attack == 'revision': properties['configuration']['activeRevisionsMode'] = 'Multiple'
    elif attack == 'http': properties['configuration']['ingress']['allowInsecure'] = True
    elif attack == 'replicas': template['scale']['maxReplicas'] = 3
    elif attack == 'scaler': template['scale']['rules'] = []
    elif attack == 'image': container['image'] = 'foreign.invalid/latest'
    elif attack == 'command': container['command'] = ['python', '-m', 'app.runtime']
    elif attack == 'sidecar': template['containers'].append(copy.deepcopy(container))
    elif attack == 'memory': container['resources']['memory'] = '4Gi'
    elif attack == 'secret': container['env'][-2]['value'] = 'DO_NOT_LOG_SECRET'
    elif attack == 'duplicate': container['env'].append(container['env'][0])
    elif attack == 'origin': container['env'][5]['value'] = '*'
    elif attack == 'probe': container['probes'][1]['httpGet']['path'] = '/ready'
    elif attack == 'storage': template['volumes'] = [{'name': 'data'}]
    with pytest.raises(Exception): review.validate(document)


@pytest.mark.parametrize('flags', [[], ['-O']])
def test_invalid_review_file_does_not_expose_contents(tmp_path, flags):
    file = tmp_path / 'review.json'; file.write_text('{"DO_NOT_LOG_SECRET":true}')
    result = subprocess.run([sys.executable, *flags, 'deploy/azure/review.py', str(file)], capture_output=True, text=True)
    assert result.returncode != 0 and result.stderr.strip() == 'Azure review configuration refused'
    assert 'DO_NOT_LOG_SECRET' not in result.stdout + result.stderr
