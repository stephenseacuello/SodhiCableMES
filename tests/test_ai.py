def test_ai_summary(client):
    r = client.get('/api/ai/summary')
    assert r.status_code == 200
    d = r.get_json()
    assert 'anomalies_detected' in d

def test_anomalies(client):
    r = client.get('/api/ai/anomalies')
    assert r.status_code == 200

def test_isolation_forest(client):
    r = client.get('/api/ai/isolation_forest')
    assert r.status_code == 200

def test_gradient_boost(client):
    r = client.get('/api/ai/gradient_boost_quality')
    assert r.status_code == 200

def test_recommendations(client):
    r = client.get('/api/ai/recommendations')
    assert r.status_code == 200

def test_nlp_status(client):
    r = client.get('/api/ai/nlp_status')
    assert r.status_code == 200
    d = r.get_json()
    assert 'sdk_installed' in d

def test_changeover(client):
    r = client.get('/api/ai/changeover_analysis')
    assert r.status_code == 200
