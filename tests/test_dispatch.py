def test_dispatch_queue(client):
    r = client.get('/api/dispatch/queue')
    assert r.status_code == 200
    d = r.get_json()
    assert 'queue' in d
    assert 'work_centers' in d

def test_scenario_list(client):
    r = client.get('/api/scenario/list')
    assert r.status_code == 200
    d = r.get_json()
    assert len(d['scenarios']) == 5
