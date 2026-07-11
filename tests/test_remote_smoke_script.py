from pathlib import Path


def test_remote_cli_smoke_script_covers_local_and_url_paths() -> None:
    script = Path("scripts/smoke_remote_cli_cs.ps1").read_text(encoding="utf-8")

    assert '[string]$ServerProfile = "local-test"' in script
    assert 'Start-Process `' in script
    assert '-WindowStyle Hidden `' in script
    assert 'Invoke-RestMethod -Uri "$BaseUrl/v1/server"' in script
    assert '$env:FLOWSCRIBE_CONFIG_DIR = $configDir' in script
    assert '& $PythonExe -m flowscribe remote add-server $ServerProfile --url $baseUrl --token $ApiToken' in script
    assert '"transcribe", $sampleMediaPath,' in script
    assert '"url", $Url,' in script
    assert 'if ($localOutput.source_kind -ne "local") {' in script
    assert 'if ([string]::IsNullOrWhiteSpace($urlOutput.transcription_strategy)) {' in script


def test_remote_cli_smoke_doc_mentions_scripted_path() -> None:
    doc = Path("docs/remote-cli-smoke-test.md").read_text(encoding="utf-8")

    assert "## Scripted path" in doc
    assert ".\\scripts\\smoke_remote_cli_cs.ps1" in doc
    assert "isolated `FLOWSCRIBE_CONFIG_DIR`" in doc
