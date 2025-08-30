import pytest
from app import app as flask_app

@pytest.fixture
def client():
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    with flask_app.test_client() as client:
        yield client

def login(client, username, password):
    return client.post('/login', data={
        'username': username,
        'password': password
    }, follow_redirects=True)

def test_chat_history_revert_flow(client):
    # Register or login as test user
    username = "testuser"
    password = "testpass"
    # Try to register (if registration endpoint exists)
    client.post('/register', data={
        'username': username,
        'password': password
    }, follow_redirects=True)
    login(client, username, password)

    # Send a few chat messages
    for i in range(3):
        resp = client.post('/chat', data={
            'message': f"Test message {i+1}"
        }, follow_redirects=True)
        assert resp.status_code == 200

    # List chat sessions (assuming endpoint exists)
    resp = client.get('/chat/sessions', follow_redirects=True)
    assert resp.status_code == 200
    assert b'session' in resp.data or b'Sessions' in resp.data

    # Parse session IDs from response (pseudo, adjust as needed)
    # This part may need to be adapted based on actual response structure
    import re
    session_ids = re.findall(rb'data-session-id="(\d+)"', resp.data)
    if not session_ids:
        # Fallback: try to find session IDs in JSON or HTML
        session_ids = re.findall(rb'session_id=(\d+)', resp.data)
    assert session_ids, "No session IDs found in session list"

    # Revert to the first session
    session_id = session_ids[0].decode()
    revert_resp = client.post(f'/chat/revert_session/{session_id}', follow_redirects=True)
    assert revert_resp.status_code == 200

    # Check that chat history is reverted (pseudo, adjust as needed)
    history_resp = client.get('/chat', follow_redirects=True)
    assert history_resp.status_code == 200
    assert b"Test message 1" in history_resp.data

if __name__ == "__main__":
    pytest.main(["-v", "test_chat.py"])