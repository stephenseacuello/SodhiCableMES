def test_kpis(client):
    r = client.get('/api/performance/kpis')
    assert r.status_code == 200
    d = r.get_json()
    assert len(d) >= 6

def test_oee_summary(client):
    r = client.get('/api/oee/summary')
    assert r.status_code == 200
    d = r.get_json()
    assert 'oee' in d

def test_oee_export(client):
    r = client.get('/api/oee/export')
    assert r.status_code == 200
    assert 'text/csv' in r.content_type

def test_shift_report_gen(client):
    r = client.post('/api/performance/generate_shift_report', json={'wc_id': 'CV-1', 'shift_code': 'Day'})
    assert r.status_code == 200
    d = r.get_json()
    assert d['ok'] is True
    assert 'oee' in d

def test_schedule_detail(client):
    r = client.get('/api/performance/schedule_detail')
    assert r.status_code == 200
