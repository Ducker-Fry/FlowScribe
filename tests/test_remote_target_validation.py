from flowscribe.gui.remote_targets import inspect_remote_target


def test_remote_target_accepts_full_http_url_with_port() -> None:
    inspection = inspect_remote_target("http://127.0.0.1:18769")

    assert inspection.valid is True
    assert inspection.resolved_url == "http://127.0.0.1:18769"
    assert "Direct URL" in inspection.message


def test_remote_target_rejects_url_without_port() -> None:
    inspection = inspect_remote_target("http://127.0.0.1")

    assert inspection.valid is False
    assert inspection.error == "Remote server URL must include an explicit port."
    assert "explicit port" in inspection.message
