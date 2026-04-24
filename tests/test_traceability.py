def test_lot_list(client):
    r = client.get('/api/traceability/lots')
    assert r.status_code == 200

def test_forward_trace(client):
    r = client.get('/api/traceability/trace?lot=CB-0330&direction=forward')
    assert r.status_code == 200
    d = r.get_json()
    assert 'trace' in d

def test_graph(client):
    r = client.get('/api/traceability/graph?lot=CB-0330&direction=forward')
    assert r.status_code == 200
    d = r.get_json()
    assert 'nodes' in d
    assert 'edges' in d

def test_risk_scored_trace(client):
    r = client.get('/api/traceability/risk_scored_trace?lot=CB-0330')
    assert r.status_code == 200
    d = r.get_json()
    assert 'total_lots' in d
    assert 'lots' in d

def test_splice_zones(client):
    r = client.get('/api/traceability/splice_zones')
    assert r.status_code == 200

def test_certificate(client):
    r = client.get('/api/traceability/certificate/WO-2026-001')
    assert r.status_code == 200
    d = r.get_json()
    assert 'compliance_spec' in d
