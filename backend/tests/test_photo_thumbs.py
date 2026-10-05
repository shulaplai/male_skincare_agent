"""`GET /api/photos/{id}?w=` — the thumbnail path (audit §7「相縮圖」).

Why: the phone home screen renders the day's photos in **96×96** cells and used to fetch
every one of them at full size. Measured on a real account: **605.9 KB** for one screen
of what the user sees as a contact sheet, because each stored photo is 768×1024 / ~65 KB.
The grid cannot look better for those bytes — the CSS box is 96 px, so a 96–336 px thumb
is already pixel-identical at 2× DPR.

What these tests pin, in the order the audit cares about:

* the **original** route is untouched (no `w` → same bytes as on disk) — the Lightbox
  still needs the real file, and every old URL has to keep working;
* `?w=` really returns that width and really is smaller;
* the width list is a **whitelist** (an arbitrary `?w=` would let anyone make the server
  decode a 1024 px JPEG once per integer — the same file, 1024 times);
* a thumb never **upscales**;
* unknown / malformed ids stay 404 (the id-shape guard is the thing keeping arbitrary
  paths out of the filesystem);
* thumbs are cacheable — otherwise every reload re-encodes them, and the win is only in
  bytes rather than in work.
"""
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.main import app
from app.photo import THUMB_WIDTHS


def jpeg(size=(1024, 1024)) -> bytes:
    """A gradient, not a flat colour: a flat patch compresses to nothing at every size,
    so the byte assertions would not mean anything."""
    img = Image.new("RGB", size)
    px = img.load()
    for y in range(size[1]):
        for x in range(0, size[0], 8):
            v = (x * 255) // size[0]
            for dx in range(min(8, size[0] - x)):
                px[x + dx, y] = (v, (y * 255) // size[1], 128)
    buf = BytesIO()
    img.save(buf, "JPEG", quality=78)
    return buf.getvalue()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    return TestClient(app)


def upload(client: TestClient, data: bytes | None = None) -> str:
    res = client.post("/api/photos", files={"file": ("p.jpg", data or jpeg(), "image/jpeg")})
    assert res.status_code == 200, res.text
    return res.json()["id"]


def served_size(body: bytes) -> tuple[int, int]:
    with Image.open(BytesIO(body)) as img:
        return img.size


def test_the_original_route_is_unchanged(client):
    pid = upload(client)
    on_disk = (Path(settings.data_dir) / "photos" / f"{pid}.jpg").read_bytes()
    res = client.get(f"/api/photos/{pid}")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/jpeg"
    assert res.content == on_disk, "冇 ?w= 就一定要係原檔，Lightbox 靠佢"
    assert served_size(res.content) == (1024, 1024)


def test_a_thumbnail_has_the_requested_width_and_fewer_bytes(client):
    pid = upload(client)
    full = client.get(f"/api/photos/{pid}").content
    thumb = client.get(f"/api/photos/{pid}?w=192")
    assert thumb.status_code == 200
    assert thumb.headers["content-type"] == "image/jpeg"
    assert served_size(thumb.content)[0] == 192
    assert served_size(thumb.content)[1] == 192, "aspect ratio 要保住（呢張係正方形）"
    assert len(thumb.content) < len(full)
    # 真正想量嘅係「同一格相下載少幾多」，唔淨係大細。
    assert len(thumb.content) * 4 < len(full), (len(thumb.content), len(full))


def test_an_arbitrary_width_is_refused(client):
    pid = upload(client)
    for bad in (1, 97, 1024, 100000):
        res = client.get(f"/api/photos/{pid}?w={bad}")
        assert res.status_code == 400, bad
        assert "96" in res.json()["detail"]
    # 唔係整數就係 FastAPI 嘅 422，唔會落到 route。
    assert client.get(f"/api/photos/{pid}?w=abc").status_code == 422


def test_every_whitelisted_width_works(client):
    pid = upload(client)
    for w in THUMB_WIDTHS:
        res = client.get(f"/api/photos/{pid}?w={w}")
        assert res.status_code == 200, w
        assert served_size(res.content)[0] == w, w


def test_a_thumbnail_never_upscales(client):
    pid = upload(client, jpeg((48, 48)))
    res = client.get(f"/api/photos/{pid}?w=336")
    assert res.status_code == 200
    assert served_size(res.content) == (48, 48), "細過要求嘅闊度就照原大細出，唔好放大"


def test_unknown_or_malformed_ids_are_404_for_both_shapes(client):
    for path in ("0" * 32, "not-a-32-hex-id", "..", "abc%2F..%2Fetc%2Fpasswd"):
        assert client.get(f"/api/photos/{path}").status_code == 404, path
        assert client.get(f"/api/photos/{path}?w=192").status_code == 404, path


def test_a_thumbnail_is_cacheable(client):
    pid = upload(client)
    res = client.get(f"/api/photos/{pid}?w=96")
    assert "max-age" in res.headers.get("cache-control", "")
    assert res.headers.get("etag") == f'"{pid}-96"', "同一個 id+闊度一定要有穩定 validator"
