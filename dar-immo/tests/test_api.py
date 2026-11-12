from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import main


@pytest.fixture
def client(tmp_path, monkeypatch):
    static = tmp_path / "static"
    static.mkdir()
    (static / "uploads").mkdir()
    (static / "index.html").write_text("<!doctype html><html lang='fr'>Dar.</html>")
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "test.sqlite3")
    monkeypatch.setattr(main, "STATIC", static)
    monkeypatch.setattr(main, "UPLOAD_DIR", static / "uploads")
    monkeypatch.setenv("DAR_SEED_DEMO", "false")
    with TestClient(main.app) as client:
        yield client


@pytest.fixture
def payload():
    return dict(
        title="Appartement lumineux avec terrasse",
        description="Un appartement agréable, lumineux et proche des transports.",
        transaction_type="vente", property_type="appartement", price=250000,
        city="Tunis", district="Cité El Khadra", surface=110, rooms=4,
        bedrooms=3, contact_name="Test Immobilier", contact_email="test@example.com",
        contact_phone="", images=[], amenities=["Terrasse", "Parking"],
    )


def create(client, payload):
    response = client.post("/api/listings", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_health_and_documentation(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").json()["info"]["version"] == "1.0.0"
    assert client.get("/").status_code == 200


def test_create_read_and_private_key(client, payload):
    created = create(client, payload)
    assert len(created["edit_token"]) >= 32
    item = created["listing"]
    assert item["title"] == payload["title"]
    assert item["is_demo"] is False
    response = client.get(f"/api/listings/{item['id']}")
    assert response.status_code == 200
    assert "edit_token" not in response.text
    assert "edit_token_hash" not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert created["edit_token"] not in client.get("/api/listings").text


def test_search_filters_sorting_and_pagination(client, payload):
    create(client, payload)
    create(client, {**payload, "title": "Villa au calme avec jardin", "city": "La Marsa", "district": "Gammarth", "property_type": "maison", "price": 800000, "surface": 250})
    create(client, {**payload, "transaction_type": "location", "price": 1500})
    assert client.get("/api/listings?q=cite").json()["total"] == 2
    assert client.get("/api/listings?city=la+marsa").json()["total"] == 1
    filtered = client.get("/api/listings?transaction_type=vente&property_type=appartement&max_price=300000&min_surface=100&min_rooms=3").json()
    assert filtered["total"] == 1
    assert client.get("/api/listings?min_price=400000").json()["total"] == 1
    page = client.get("/api/listings?sort=price_asc&limit=2").json()
    assert page["total"] == 3
    assert len(page["items"]) == 2
    assert page["items"][0]["price"] == 1500
    assert len(client.get("/api/listings?limit=2&offset=2").json()["items"]) == 1
    assert client.get("/api/listings?sort=price_desc").json()["items"][0]["price"] == 800000
    assert client.get("/api/listings?sort=surface_desc").json()["items"][0]["surface"] == 250
    assert client.get("/api/listings", params={"q": "' OR 1=1 --"}).json()["total"] == 0
    assert client.get("/api/listings?min_price=100&max_price=10").status_code == 422
    assert client.get("/api/listings?limit=10000").status_code == 422


def test_ids_filter_for_favorites_and_management(client, payload):
    created = create(client, payload)
    item_id = created["listing"]["id"]
    assert client.get("/api/listings", params={"ids": item_id}).json()["total"] == 1
    assert client.get("/api/listings?ids=").json()["total"] == 0
    assert client.get("/api/listings?ids=unknown").json()["total"] == 0


@pytest.mark.parametrize("changes", [
    {"title": "abc"}, {"title": "      "}, {"description": "Trop court"},
    {"price": -1}, {"surface": 0}, {"bedrooms": 5},
    {"contact_email": "pas-un-email"}, {"contact_email": "", "contact_phone": ""},
    {"contact_phone": "javascript:alert(1)"}, {"contact_phone": "+12"},
    {"property_type": "chateau"}, {"transaction_type": "achat"},
    {"images": ["https://example.com/photo.jpg"]},
    {"images": ["/static/uploads/../../secret.jpg"]},
    {"images": ["/static/images/introuvable.jpg"]},
    {"amenities": ["Équipement non valide"]}, {"is_demo": True},
])
def test_invalid_data_rejected(client, payload, changes):
    response = client.post("/api/listings", json={**payload, **changes})
    assert response.status_code == 422
    assert "detail" in response.json()
    assert client.get("/api/listings").json()["total"] == 0


def test_updates_need_the_correct_key(client, payload):
    created = create(client, payload)
    url = f"/api/listings/{created['listing']['id']}"
    changed = {**payload, "price": 260000, "title": "Nouveau titre pour mon appartement"}
    assert client.put(url, json=changed).status_code == 403
    assert client.put(url, json=changed, headers={"X-Edit-Token": "incorrect"}).status_code == 403
    response = client.put(url, json=changed, headers={"X-Edit-Token": created["edit_token"]})
    assert response.status_code == 200
    assert response.json()["price"] == 260000
    assert response.json()["created_at"] == created["listing"]["created_at"]
    assert "edit_token" not in response.text


def test_delete_needs_key_and_removes_listing(client, payload):
    created = create(client, payload)
    url = f"/api/listings/{created['listing']['id']}"
    assert client.delete(url).status_code == 403
    assert client.delete(url, headers={"X-Edit-Token": "wrong"}).status_code == 403
    response = client.delete(url, headers={"X-Edit-Token": created["edit_token"]})
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(url).status_code == 404
    assert client.get("/api/stats").json()["total"] == 0


def test_stats(client, payload):
    create(client, payload)
    create(client, {**payload, "transaction_type": "location", "city": "Sousse", "price": 1000})
    stats = client.get("/api/stats").json()
    assert (stats["total"], stats["vente"], stats["location"], stats["cities"]) == (2, 1, 1, 2)
    assert stats["city_names"] == ["Sousse", "Tunis"]


def test_upload_and_use_photo(client, payload):
    stream = BytesIO()
    Image.new("RGBA", (100, 100), (0, 128, 0, 180)).save(stream, "PNG")
    response = client.post("/api/uploads", files={"file": ("photo.png", stream.getvalue(), "image/png")})
    assert response.status_code == 201
    url = response.json()["url"]
    path = main.STATIC / url.removeprefix("/static/")
    with Image.open(path) as image:
        assert image.format == "JPEG"
        assert image.mode == "RGB"
        assert not image.getexif()
    created = create(client, {**payload, "images": [url]})
    assert created["listing"]["images"] == [url]


def test_upload_rejects_scripts_and_oversized_files(client):
    response = client.post("/api/uploads", files={"file": ("photo.svg", b'<svg onload="alert(1)"></svg>', "image/svg+xml")})
    assert response.status_code == 415
    response = client.post("/api/uploads", files={"file": ("photo.jpg", b"x" * (main.MAX_UPLOAD + 1), "image/jpeg")})
    assert response.status_code == 413


def test_database_persists_and_seed_is_inserted_once(client, monkeypatch):
    monkeypatch.setenv("DAR_SEED_DEMO", "true")
    main.initialize_database()
    assert client.get("/api/listings").json()["total"] == 6
    main.initialize_database()
    assert client.get("/api/listings").json()["total"] == 6
    demo_id = client.get("/api/listings").json()["items"][0]["id"]
    assert client.delete(f"/api/listings/{demo_id}", headers={"X-Edit-Token": "any"}).status_code == 403
    with main.connection() as conn:
        conn.execute("DELETE FROM listings")
    main.initialize_database()
    assert client.get("/api/listings").json()["total"] == 0


def test_not_found(client):
    assert client.get("/api/listings/unknown").status_code == 404
