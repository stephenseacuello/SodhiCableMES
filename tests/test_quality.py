def test_spc_data(client):
    r = client.get('/api/quality/spc')
    assert r.status_code == 200
    d = r.get_json()
    assert 'readings' in d

def test_cpk(client):
    r = client.get('/api/quality/cpk')
    assert r.status_code == 200

def test_ncr_list(client):
    r = client.get('/api/quality/ncr')
    assert r.status_code == 200

def test_ncr_create(client):
    r = client.post('/api/quality/ncr/create', json={'defect_type': 'Test', 'severity': 'Minor'})
    assert r.status_code == 200
    assert r.get_json()['ok'] is True

def test_scrap_create(client):
    r = client.post('/api/quality/scrap/create', json={'cause_code': 'STARTUP', 'quantity_ft': 100})
    assert r.status_code == 200
