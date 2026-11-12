from dataclasses import replace
import json
import time

from fastapi.testclient import TestClient
import pytest
from starlette.websockets import WebSocketDisconnect

from backend.main import create_app
from backend.store import Store
from backend.tests.conftest import FakeDetector, NAMES, zone_payload


def test_classes_are_dynamic_and_foot_cannot_be_required(client):
    info = client.get('/api/classes').json()
    assert info['class_count'] == 10 and info['classes'][6]['name'] == 'helmet'
    for invalid in (3, 0, 99):
        payload = zone_payload(); payload['required_class_ids'] = [invalid]
        assert client.post('/api/zones', json=payload).status_code == 422


def test_zone_crud_versions_and_persistence(client, settings):
    created = client.post('/api/zones', json=zone_payload())
    assert created.status_code == 201
    zone = created.json()
    updated = client.patch('/api/zones/' + zone['id'], json={'enabled': False, 'expected_version': 1})
    assert updated.status_code == 200 and updated.json()['version'] == 2
    assert client.patch('/api/zones/' + zone['id'], json={'enabled': True, 'expected_version': 1}).status_code == 409
    assert Store(settings, NAMES).zone(zone['id']).enabled is False
    assert client.delete('/api/zones/' + zone['id']).status_code == 204
    assert client.get('/api/zones?source_id=test-video').json()['items'] == []


def test_bad_zone_inputs(client):
    for changes in ({'required_class_ids': []}, {'kind': 'restricted', 'required_class_ids': [6]}, {'rect': {'x1': .8,'y1':0,'x2':.2,'y2':1}}, {'name':'   '}):
        assert client.post('/api/zones', json={**zone_payload(), **changes}).status_code == 422


def test_upload_validation_limits_and_managed_filenames(client, video_bytes):
    assert client.post('/api/videos', files={'file': ('model.pt', b'pickle','application/octet-stream')}).status_code == 400
    assert client.post('/api/videos', files={'file': ('invalid.mp4', b'not a video','video/mp4')}).status_code == 400
    assert client.post('/api/videos', files={'file': ('huge.mp4', b'x' * 2_000_000,'video/mp4')}).status_code == 413
    uploaded = client.post('/api/videos', files={'file': ('../../unsafe.mp4', video_bytes,'video/mp4')})
    assert uploaded.status_code == 201
    value = uploaded.json()
    assert value['name'] == 'unsafe.mp4'
    filenames = [path.name for path in client.app.state.store.uploads.iterdir()]
    assert filenames == [value['id'] + '.mp4']


def test_stream_pair_alerts_snapshots_ack_and_hot_zone_edit(client, video_bytes):
    video = client.post('/api/videos', files={'file': ('fixture.mp4', video_bytes,'video/mp4')}).json()
    ppe = client.post('/api/zones', json=zone_payload(video['id'])).json()
    restricted = client.post('/api/zones', json=zone_payload(video['id'], 'restricted')).json()
    with client.websocket_connect('/ws/stream', subprotocols=['safety-stream']) as socket:
        assert socket.receive_json()['has_frame'] is False
        response = client.post('/api/stream/start', json={'kind':'video','video_id':video['id'],'loop':True})
        assert response.status_code == 200
        for _ in range(30):
            packet = socket.receive_json()
            if packet.get('has_frame'):
                image = socket.receive_bytes()
                assert image.startswith(b'\xff\xd8')
                break
        else:
            pytest.fail('No video frame received')
        assert len(packet['violations']) == 3
        assert len(packet['alerts']) == 3
        missing = next(alert for alert in packet['alerts'] if alert['kind'] == 'missing_ppe')
        assert missing['missing_classes'] == ['safety-vest']
        assert client.get(missing['snapshot_url']).content.startswith(b'\xff\xd8')
        assert client.post('/api/alerts/' + missing['id'] + '/acknowledge').status_code == 200
        assert client.get('/api/alerts?acknowledged=true').json()['total'] == 1
        assert client.post('/api/stream/pause').status_code == 200
        assert client.patch('/api/zones/' + ppe['id'], json={'enabled':False,'expected_version':1}).status_code == 200
        status = client.get('/api/status').json()
        assert status['state'] == 'paused'
        assert all(item['zone_id'] != ppe['id'] for item in status['violations'])
        assert client.delete('/api/zones/' + restricted['id']).status_code == 204
        assert client.get('/api/status').json()['violations'] == []
        assert client.post('/api/stream/resume').status_code == 200
        assert client.post('/api/stream/stop').status_code == 200
        assert client.get('/api/status').json()['state'] == 'stopped'


def test_authentication_http_websocket_and_origin(settings):
    configured = replace(settings, api_token='test_token_with_more_than_32_characters')
    with TestClient(create_app(configured, FakeDetector)) as client:
        assert client.get('/health').status_code == 200
        assert client.get('/api/classes').status_code == 401
        headers = {'Authorization': 'Bearer ' + configured.api_token}
        assert client.get('/api/classes', headers=headers).status_code == 200
        assert client.get('/api/classes', headers={**headers,'Origin':'https://untrusted.example'}).status_code == 403
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect('/ws/stream'):
                pass
        assert error.value.code == 4401
        with client.websocket_connect('/ws/stream', subprotocols=['safety-stream','bearer.' + configured.api_token]) as socket:
            assert socket.receive_json()['state'] == 'idle'
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect('/ws/stream', headers={'Origin':'https://untrusted.example'}, subprotocols=['safety-stream','bearer.' + configured.api_token]):
                pass
        assert error.value.code == 4403


def test_settings_and_alert_filters(client):
    assert client.put('/api/settings', json={'confidence':.7,'association_threshold':.6,'resolve_after_seconds':2}).status_code == 200
    assert client.get('/api/settings').json()['confidence'] == .7
    assert client.put('/api/settings', json={'confidence':2}).status_code == 422
    assert client.get('/api/alerts?kind=invalid').status_code == 422
    assert client.get('/api/alerts/export').status_code == 200


def test_restart_closes_interrupted_alerts_without_claiming_compliance(settings):
    store = Store(settings, NAMES)
    store.add_alert({'source_id':'test-video','zone_id':'test-zone','kind':'intrusion'}, None)
    with TestClient(create_app(settings, FakeDetector)) as client:
        alert = client.get('/api/alerts').json()['items'][0]
        assert alert['resolved_at'] is not None
        assert alert['resolution_reason'] == 'monitoring_restarted'
        assert client.get('/api/status').json()['active_alert_count'] == 0


def test_chunked_upload_cannot_bypass_the_request_limit(client):
    def chunks():
        yield b'--limit\r\nContent-Disposition: form-data; name="file"; filename="huge.mp4"\r\nContent-Type: video/mp4\r\n\r\n'
        for _ in range(20):
            yield b'x' * 100_000
        yield b'\r\n--limit--\r\n'
    response = client.post('/api/videos', content=chunks(), headers={'Content-Type':'multipart/form-data; boundary=limit'})
    assert response.status_code == 413
