from flowscribe.execution.remote_config import RemoteServerProfile, resolve_remote_server, save_remote_server_profiles
from flowscribe.gui.remote_targets import inspect_remote_target


def test_remote_target_accepts_full_http_url_with_port(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("FLOWSCRIBE_CONFIG_DIR", str(tmp_path / "config"))
    inspection = inspect_remote_target("http://127.0.0.1:18769")

    assert inspection.valid is True
    assert inspection.resolved_url == "http://127.0.0.1:18769"
    assert "Direct URL" in inspection.message


def test_remote_target_matches_saved_profile_by_url(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("FLOWSCRIBE_CONFIG_DIR", str(tmp_path / "config"))
    save_remote_server_profiles(
        (
            RemoteServerProfile(
                name="aliyun-bj",
                base_url="http://39.106.206.25:8765",
                token="secret-token",
            ),
        )
    )

    inspection = inspect_remote_target("http://39.106.206.25:8765")

    assert inspection.valid is True
    assert inspection.resolved_url == "http://39.106.206.25:8765"
    assert inspection.profile_name == "aliyun-bj"
    assert "Matched saved profile: aliyun-bj" in inspection.message


def test_resolve_remote_server_inherits_matching_profile_token(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("FLOWSCRIBE_CONFIG_DIR", str(tmp_path / "config"))
    save_remote_server_profiles(
        (
            RemoteServerProfile(
                name="aliyun-bj",
                base_url="http://39.106.206.25:8765",
                token="secret-token",
                remote_cookies_path="/home/fry/.flowscribe-secrets/bilibili.cookies.txt",
                timeout_seconds=45.0,
                download_artifacts_by_default=False,
            ),
        )
    )

    resolved = resolve_remote_server("http://39.106.206.25:8765")

    assert resolved.name == "aliyun-bj"
    assert resolved.base_url == "http://39.106.206.25:8765"
    assert resolved.token == "secret-token"
    assert resolved.remote_cookies_path == "/home/fry/.flowscribe-secrets/bilibili.cookies.txt"
    assert resolved.timeout_seconds == 45.0
    assert resolved.download_artifacts_by_default is False


def test_remote_target_rejects_url_without_port() -> None:
    inspection = inspect_remote_target("http://127.0.0.1")

    assert inspection.valid is False
    assert inspection.error == "Remote server URL must include an explicit port."
    assert "explicit port" in inspection.message
