def test_health(client):
    r = client.get('/api/health')
    assert r.status_code == 200
    d = r.get_json()
    assert d['status'] == 'healthy'
    assert d['db_connected'] is True

def test_search(client):
    r = client.get('/api/search?q=CV-1')
    assert r.status_code == 200
    d = r.get_json()
    assert d['total'] > 0
    assert 'equipment' in d['results']

def test_search_short_query(client):
    r = client.get('/api/search?q=C')
    d = r.get_json()
    assert d['results'] == {} or d.get('total', 0) == 0

def test_notifications(client):
    r = client.get('/api/notifications')
    assert r.status_code == 200
    d = r.get_json()
    assert 'count' in d
    assert 'items' in d
