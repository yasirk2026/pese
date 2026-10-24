import base64
import pytest
from fastapi.testclient import TestClient
from engine.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_profile_api_endpoints(client: TestClient):
    # 1. GET /api/profile
    res = client.get("/api/profile")
    assert res.status_code == 200
    data = res.json()
    assert "schema_version" in data
    assert "display_name" in data

    # 2. POST /api/profile
    res = client.post("/api/profile", json={"display_name": "Yasir Tester", "about": "Building PESE"})
    assert res.status_code == 200
    assert res.json()["display_name"] == "Yasir Tester"
    assert res.json()["about"] == "Building PESE"

    # 3. POST /api/profile/avatar
    dummy_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    b64_str = "data:image/png;base64," + base64.b64encode(dummy_png).decode("utf-8")
    res = client.post("/api/profile/avatar", json={"image_base64": b64_str, "filename": "test.png"})
    assert res.status_code == 200
    avatar = res.json()["avatar"]
    assert avatar is not None
    assert avatar["relative_path"] == "profile/avatar.png"

    # 4. GET /api/profile/avatar
    res = client.get("/api/profile/avatar")
    assert res.status_code == 200
    assert res.content == dummy_png

    # 5. DELETE /api/profile/avatar
    res = client.delete("/api/profile/avatar")
    assert res.status_code == 200
    assert res.json()["avatar"] is None

    # 6. GET /api/profile/avatar should now 404
    res = client.get("/api/profile/avatar")
    assert res.status_code == 404
