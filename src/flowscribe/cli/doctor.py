"""Environment checks for FlowScribe."""

from __future__ import annotations

import importlib.metadata
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from flowscribe.engine.pipe_client import FlowScribeEngineClient, pywintypes, win32file
from flowscribe.media.tools import resolve_tool_path
from flowscribe.providers.transcribe.native_engine import resolve_engine_exe


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    ok: bool
    message: str

    @property
    def marker(self) -> str:
        return "OK" if self.ok else "FAIL"


def run_doctor(
    *,
    output_dir: Path,
    provider_name: str,
    model_name: str,
    hello_smoke: bool = False,
    skip_model_access: bool = False,
    print_result: bool = True,
) -> int:
    checks = [check_python_version(), check_command("ffmpeg"), check_command("ffprobe"), check_output_dir(output_dir)]
    if provider_name == "native-engine":
        checks.extend(
            [
                check_pywin32_import(),
                check_native_engine_exe(),
                check_native_model_path(model_name),
            ]
        )
        if hello_smoke:
            checks.append(check_native_engine_hello_smoke())
    else:
        checks.append(check_faster_whisper_import())
        if skip_model_access:
            checks.append(
                DoctorCheck(
                    "Model access",
                    True,
                    "skipped by --skip-model-access; remote model reachability was not checked",
                )
            )
        else:
            checks.append(check_model_download(model_name))

    if print_result:
        print("FlowScribe doctor")
        print("=================")
        print(f"Provider: {provider_name}")
        for check in checks:
            print(f"[{check.marker}] {check.name}: {check.message}")

    return 0 if all(check.ok for check in checks) else 1


def check_python_version() -> DoctorCheck:
    version = sys.version_info
    current = f"{version.major}.{version.minor}.{version.micro}"
    if version >= (3, 10):
        return DoctorCheck("Python", True, f"{current} is supported")
    return DoctorCheck("Python", False, f"{current} is unsupported; Python 3.10+ is required")


def check_command(command: str) -> DoctorCheck:
    executable = resolve_tool_path(command)
    if executable == command:
        return DoctorCheck(command, False, f"{command} was not found on PATH")

    try:
        completed = subprocess.run(
            [executable, "-version"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return DoctorCheck(command, False, f"found at {executable}, but execution failed: {exc}")

    first_line = (completed.stdout or completed.stderr).splitlines()[0]
    return DoctorCheck(command, True, f"{first_line} ({executable})")


def check_faster_whisper_import() -> DoctorCheck:
    try:
        __import__("faster_whisper")
    except ImportError as exc:
        return DoctorCheck(
            "faster-whisper",
            False,
            f"not importable: {exc}. Run `python -m pip install -e .[dev]`.",
        )

    try:
        version = importlib.metadata.version("faster-whisper")
    except importlib.metadata.PackageNotFoundError:
        version = "installed"
    return DoctorCheck("faster-whisper", True, f"importable, version {version}")


def check_pywin32_import() -> DoctorCheck:
    if pywintypes is None or win32file is None:
        return DoctorCheck(
            "pywin32",
            False,
            "not importable. Install pywin32 to use native-engine named pipe integration.",
        )
    return DoctorCheck("pywin32", True, "importable")


def check_output_dir(output_dir: Path) -> DoctorCheck:
    path = output_dir.expanduser().resolve()
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path,
            prefix=".flowscribe-doctor-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write("FlowScribe doctor write test")
        temp_path.unlink(missing_ok=True)
    except OSError as exc:
        return DoctorCheck("Output directory", False, f"{path} is not writable: {exc}")

    return DoctorCheck("Output directory", True, f"{path} is writable")


def check_model_download(model_name: str) -> DoctorCheck:
    model_path = Path(model_name).expanduser()
    if model_path.exists():
        return DoctorCheck("Model access", True, f"local model path exists: {model_path.resolve()}")

    repo_id = resolve_faster_whisper_repo(model_name)
    if repo_id is None:
        return DoctorCheck(
            "Model access",
            False,
            f"cannot infer Hugging Face repo for model `{model_name}`; use a local path or known model name",
        )

    url = f"https://huggingface.co/{repo_id}/resolve/main/config.json"
    request = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status = getattr(response, "status", 200)
    except urllib.error.HTTPError as exc:
        return DoctorCheck("Model access", False, f"{repo_id} is not reachable: HTTP {exc.code}")
    except urllib.error.URLError as exc:
        return DoctorCheck("Model access", False, f"{repo_id} is not reachable: {exc.reason}")
    except TimeoutError:
        return DoctorCheck("Model access", False, f"{repo_id} check timed out")

    if 200 <= status < 400:
        return DoctorCheck("Model access", True, f"{repo_id} is reachable")
    return DoctorCheck("Model access", False, f"{repo_id} returned HTTP {status}")


def check_native_engine_exe() -> DoctorCheck:
    try:
        engine_exe = resolve_engine_exe()
    except Exception as exc:
        return DoctorCheck(
            "Native engine executable",
            False,
            f"{exc}. Build native/flowscribe-engine or set FLOWSCRIBE_ENGINE_EXE.",
        )
    return DoctorCheck("Native engine executable", True, f"found: {engine_exe}")


def check_native_model_path(model_name: str) -> DoctorCheck:
    model_path = Path(model_name).expanduser()
    if not model_path.exists() or not model_path.is_file():
        return DoctorCheck(
            "Native model path",
            False,
            "native-engine requires --model to point to an existing local whisper.cpp ggml .bin file.",
        )
    if model_path.suffix.lower() != ".bin":
        return DoctorCheck(
            "Native model path",
            False,
            f"{model_path} is not a .bin file. native-engine requires a whisper.cpp ggml .bin model.",
        )
    return DoctorCheck("Native model path", True, f"local ggml model exists: {model_path.resolve()}")


def check_native_engine_hello_smoke() -> DoctorCheck:
    try:
        engine_exe = resolve_engine_exe()
    except Exception as exc:
        return DoctorCheck("Native hello smoke", False, f"cannot start smoke check: {exc}")

    try:
        proc = subprocess.Popen(
            [str(engine_exe)],
            cwd=str(engine_exe.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        return DoctorCheck("Native hello smoke", False, f"failed to launch engine: {exc}")

    client = FlowScribeEngineClient(timeout=1.0)
    try:
        if not client.connect(retry=40, delay=0.05):
            return DoctorCheck(
                "Native hello smoke",
                False,
                "failed to connect to native-engine pipe after launch.",
            )
        hello = client.send_hello()
        if not hello or not hello.get("ok"):
            return DoctorCheck("Native hello smoke", False, f"hello failed: {hello}")
        return DoctorCheck("Native hello smoke", True, "launch and hello round-trip succeeded")
    finally:
        client.close()
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def resolve_faster_whisper_repo(model_name: str) -> str | None:
    known = {
        "tiny",
        "tiny.en",
        "base",
        "base.en",
        "small",
        "small.en",
        "medium",
        "medium.en",
        "large-v1",
        "large-v2",
        "large-v3",
        "large-v3-turbo",
    }
    if model_name in known:
        return f"Systran/faster-whisper-{model_name}"
    if "/" in model_name:
        return model_name
    return None
