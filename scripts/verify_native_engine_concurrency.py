from __future__ import annotations

import argparse
import logging
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from flowscribe.engine.pipe_client import FlowScribeEngineClient


ROOT = Path(__file__).resolve().parents[1]
ENGINE_EXE = ROOT / "native" / "flowscribe-engine" / "build" / "Debug" / "flowscribe-engine.exe"


def run_ffmpeg(video_path: Path, wav_path: Path, seconds: float) -> None:
    command = [
        "ffmpeg",
        "-y",
    ]
    if seconds > 0:
        command.extend(["-t", str(seconds)])
    command.extend(
        [
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(wav_path),
        ]
    )
    subprocess.run(
        command,
        check=True,
    )


def pump_output(proc: subprocess.Popen[str], output_queue: queue.Queue[str]) -> None:
    if proc.stdout is None:
        return
    for line in proc.stdout:
        text = line.rstrip()
        output_queue.put(text)
        print(f"[engine] {text}", flush=True)


def wait_for_all_results(
    client: FlowScribeEngineClient,
    job_ids: list[str],
    timeout: float,
) -> dict[str, tuple[int, dict]]:
    deadline = time.monotonic() + timeout
    pending = set(job_ids)
    results: dict[str, tuple[int, dict]] = {}
    original_timeout = client.timeout
    client.timeout = 1.0
    try:
        next_status_at = 0.0
        while pending and time.monotonic() < deadline:
            response = client.recv_message()
            if response is None:
                now = time.monotonic()
                if now >= next_status_at:
                    for job_id in sorted(pending):
                        query = client.query_job(job_id)
                        print(f"status: {job_id} -> {query}", flush=True)
                    next_status_at = now + 15.0
                continue

            kind, payload = response
            job_id = payload.get("job_id")
            if job_id in pending:
                print(f"message: {job_id} kind=0x{kind:04x} payload={payload}", flush=True)
                if kind in (0x0031, 0x0032):
                    results[job_id] = (kind, payload)
                    pending.remove(job_id)

        if pending:
            raise TimeoutError(f"timed out waiting for {sorted(pending)}")
        return results
    finally:
        client.timeout = original_timeout


def main() -> int:
    logging.getLogger("flowscribe.engine.pipe_client").setLevel(logging.CRITICAL)

    parser = argparse.ArgumentParser(description="Verify native engine worker/runtime concurrency.")
    parser.add_argument("--video", default=r"E:\Draft\VID_20250317_205031.mp4")
    parser.add_argument("--model", default=str(ROOT / "models" / "ggml-base.en.bin"))
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--seconds", type=float, default=45.0)
    parser.add_argument("--timeout", type=float, default=600.0)
    args = parser.parse_args()

    video_path = Path(args.video)
    model_path = Path(args.model)
    if not ENGINE_EXE.exists():
        raise FileNotFoundError(ENGINE_EXE)
    if not video_path.exists():
        raise FileNotFoundError(video_path)
    if not model_path.exists():
        raise FileNotFoundError(model_path)

    with tempfile.TemporaryDirectory(prefix="flowscribe-native-concurrency-") as temp_dir:
        temp_path = Path(temp_dir)
        wav_path = temp_path / "input.wav"
        log_path = temp_path / "engine.log"

        print(f"extracting audio: {video_path} -> {wav_path} seconds={args.seconds}", flush=True)
        run_ffmpeg(video_path, wav_path, args.seconds)
        print(f"audio ready: {wav_path} bytes={wav_path.stat().st_size}", flush=True)

        env = os.environ.copy()
        env["FLOWSCRIBE_ENGINE_VERBOSE"] = "1"
        env["FLOWSCRIBE_ENGINE_WORKER_COUNT"] = str(args.jobs)
        env["FLOWSCRIBE_ENGINE_RUNTIME_MAX_COUNT"] = str(args.jobs)

        print(f"starting engine: {ENGINE_EXE}", flush=True)
        output_queue: queue.Queue[str] = queue.Queue()
        proc = subprocess.Popen(
            [str(ENGINE_EXE)],
            cwd=str(ENGINE_EXE.parent),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        output_thread = threading.Thread(target=pump_output, args=(proc, output_queue), daemon=True)
        output_thread.start()

        client = FlowScribeEngineClient(timeout=30.0)
        try:
            if not client.connect(retry=60, delay=0.1):
                raise RuntimeError("failed to connect to engine")

            hello = client.send_hello()
            if not hello or not hello.get("ok"):
                raise RuntimeError(f"hello failed: {hello}")
            print(f"hello: {hello}", flush=True)

            print(f"loading model: {model_path}", flush=True)
            load = client.load_model(str(model_path), model_path.stem, use_gpu=False)
            if not load or not load.get("ok"):
                raise RuntimeError(f"load failed: {load}")
            print(f"model loaded: {load}", flush=True)

            job_ids = [f"job-real-{i + 1}" for i in range(args.jobs)]
            for job_id in job_ids:
                submit = client.submit_job(
                    job_id=job_id,
                    audio_path=str(wav_path),
                    language="en",
                    task="transcribe",
                    beam_size=1,
                )
                if not submit or not submit.get("ok"):
                    raise RuntimeError(f"submit failed for {job_id}: {submit}")
                print(f"submitted: {job_id}", flush=True)

            results = wait_for_all_results(client, job_ids, args.timeout)
            for job_id, (kind, _payload) in results.items():
                print(f"completed message: {job_id} kind=0x{kind:04x}", flush=True)

            for job_id, (kind, payload) in results.items():
                if kind != 0x0031:
                    raise RuntimeError(f"{job_id} failed: {payload}")
                query = client.query_job(job_id)
                print(f"final query: {job_id} -> {query}", flush=True)
                if not query or query.get("job", {}).get("status") != "completed":
                    raise RuntimeError(f"{job_id} did not complete: {query}")

        finally:
            client.close()
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)
            output_thread.join(timeout=2)

        log_lines: list[str] = []
        while not output_queue.empty():
            log_lines.append(output_queue.get())
        log_text = "\n".join(log_lines)
        log_path.write_text(log_text, encoding="utf-8")
        print(f"engine log: {log_path}", flush=True)
        print(log_text, flush=True)

        required = [
            "worker started: 0",
            "worker started: 1",
            "runtime pool loaded: count=2",
            "runtime slot acquired: index=0",
            "runtime slot acquired: index=1",
            "whisper transcribe started: job-real-1",
            "whisper transcribe started: job-real-2",
        ]
        missing = [text for text in required if text not in log_text]
        if missing:
            raise RuntimeError(f"missing expected log markers: {missing}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
