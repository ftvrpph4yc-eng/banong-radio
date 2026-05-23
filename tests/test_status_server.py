from banong_radio.status_server import dashboard_url
from banong_radio.status_server import WEB_ROOT


def test_dashboard_url_normalizes_public_bind_hosts() -> None:
    assert dashboard_url("0.0.0.0", 8765) == "http://127.0.0.1:8765/"
    assert dashboard_url("::", 8765) == "http://127.0.0.1:8765/"
    assert dashboard_url("localhost", 8765) == "http://localhost:8765/"


def test_status_screen_keeps_live_dashboard_contract() -> None:
    html = (WEB_ROOT / "status_screen.html").read_text(encoding="utf-8")

    for element_id in [
        "onAirLabel",
        "currentSegment",
        "musicPrompt",
        "playlistProgress",
        "modePill",
        "requestedSource",
        "statusPath",
        "pollState",
    ]:
        assert f'id="{element_id}"' in html

    assert 'fetch(`/status.json?t=${Date.now()}`' in html
    assert 'window.location.protocol === "file:"' in html
    assert "PREVIEW_STATUS" in html
