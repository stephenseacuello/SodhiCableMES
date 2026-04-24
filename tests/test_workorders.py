def test_wo_list(client):
    r = client.get('/api/workorders/list')
    assert r.status_code == 200
    assert len(r.get_json()) > 0

def test_wo_create_validation(client):
    r = client.post('/api/workorders/create', json={})
    assert r.status_code == 400

def test_wo_create_bad_product(client):
    r = client.post('/api/workorders/create', json={'product_id': 'FAKE', 'order_qty_kft': 10})
    assert r.status_code == 400

def test_wo_create_success(client):
    r = client.post('/api/workorders/create', json={'product_id': 'INST-3C16-FBS', 'order_qty_kft': 5, 'priority': 3})
    assert r.status_code == 200
    d = r.get_json()
    assert d['ok'] is True
    assert 'wo_id' in d
    assert 'lot_number' in d

def test_wo_detail(client):
    r = client.get('/api/workorders/WO-2026-001')
    assert r.status_code == 200
    d = r.get_json()
    assert 'work_order' in d
    assert 'operations' in d

def test_wo_export(client):
    r = client.get('/api/workorders/export')
    assert r.status_code == 200
    assert 'text/csv' in r.content_type
