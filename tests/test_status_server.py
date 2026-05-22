from banong_radio.status_server import dashboard_url


def test_dashboard_url_normalizes_public_bind_hosts() -> None:
    assert dashboard_url("0.0.0.0", 8765) == "http://127.0.0.1:8765/"
    assert dashboard_url("::", 8765) == "http://127.0.0.1:8765/"
    assert dashboard_url("localhost", 8765) == "http://localhost:8765/"
