import io
import pytest
from app import create_app, db

@pytest.fixture()
def client(tmp_path):
    app = create_app({"TESTING": True, "SECRET_KEY": "test", "DATABASE": str(tmp_path/"t.sqlite"), "UPLOAD_FOLDER": str(tmp_path/"uploads")})
    with app.test_client() as c: yield c

def register(c, email="a@example.com", password="Password1!"):
    return c.post("/register", data={"email":email,"name":"A","password":password}, follow_redirects=True)

def test_registration_and_login(client):
    r = register(client); assert r.status_code == 200
    assert b"Dashboard" not in r.data
    client.get("/logout")
    r = client.post("/login", data={"email":"a@example.com","password":"Password1!"}, follow_redirects=True)
    assert b"Dashboard" not in r.data  # citizens cannot access operations

def test_public_report_and_map(client):
    r = client.post("/report", data={"type":"Пожар","title":"Test","description":"Smoke","latitude":"41.9","longitude":"21.4","photo":(io.BytesIO(b"not image"),"x.txt")}, follow_redirects=True)
    assert "Фото".encode() in r.data
    r = client.post("/report", data={"type":"Пожар","title":"Test","description":"Smoke","latitude":"41.9","longitude":"21.4"})
    assert r.status_code == 302
    assert client.get("/api/incidents").json[0]["title"] == "Test"

def test_anonymous_report_does_not_store_identity(client):
    client.post("/report", data={
        "type": "forest_fire",
        "title": "Anonymous",
        "description": "Smoke",
        "latitude": "41.9",
        "longitude": "21.4",
        "anonymous": "on",
        "reporter_name": "Should not persist",
        "contact": "should-not-persist@example.com",
    })
    with client.application.app_context():
        row = db().execute("SELECT reporter_name, contact, created_by FROM incidents WHERE title=?", ("Anonymous",)).fetchone()
    assert row["reporter_name"] == ""
    assert row["contact"] == ""
    assert row["created_by"] is None

def test_staff_notifications_are_created_for_public_report(client):
    with client.application.app_context():
        db().execute(
            "INSERT INTO users(email,password_hash,name,role,created_at) VALUES (?,?,?,?,?)",
            ("police@example.com", "hash", "Police", "police", "now"),
        )
        db().commit()
    client.post("/report", data={
        "type": "flood", "title": "Flood", "description": "Water",
        "latitude": "41.9", "longitude": "21.4", "anonymous": "on",
    })
    client.post("/login", data={"email": "police@example.com", "password": "wrong"})
    with client.application.app_context():
        count = db().execute("SELECT COUNT(*) FROM notifications WHERE kind='new_incident'").fetchone()[0]
    assert count == 1

def test_dashboard_requires_role(client):
    assert client.get("/dashboard").status_code == 302
    register(client)
    assert client.get("/dashboard").status_code == 403
