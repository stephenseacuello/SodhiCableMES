def test_plant_overview(client):
    r = client.get('/api/scada/plant_overview')
    assert r.status_code == 200
    assert len(r.get_json()) >= 25

def test_wc_detail(client):
    r = client.get('/api/scada/workcenter/CV-1')
    assert r.status_code == 200
    d = r.get_json()
    assert 'wc_info' in d
    assert 'equipment' in d

def test_energy(client):
    r = client.get('/api/scada/energy/CV-1')
    assert r.status_code == 200

def test_plc_status(client):
    r = client.get('/api/scada/plc_status/CV-1')
    assert r.status_code == 200

def test_spark_tests(client):
    r = client.get('/api/scada/spark_tests/TEST-1')
    assert r.status_code == 200
    d = r.get_json()
    assert 'pass_rate' in d

def test_system_metrics(client):
    r = client.get('/api/system/metrics')
    assert r.status_code == 200
    d = r.get_json()
    assert d['tables'] >= 70
    assert d['endpoints'] >= 200
