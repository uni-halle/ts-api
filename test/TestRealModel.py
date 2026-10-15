"""
Tests with a real faster-whisper model, enabled with
TSAPI_REAL_MODEL_TESTS=1. The model (TSAPI_TEST_MODEL, default "tiny") is
downloaded once from Hugging Face into TSAPI_TEST_MODEL_DIR. The audio files
are part of the repository, see test/data/audio/README.md.
"""
import base64
import importlib
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from core.Transcriber import Transcriber
from core.TsApi import TsApi
from packages.File import File
from utils.database import JobStatus

pytestmark = pytest.mark.skipif(
    os.environ.get("TSAPI_REAL_MODEL_TESTS") != "1",
    reason="set TSAPI_REAL_MODEL_TESTS=1 to run tests with a real model")

AUDIO = Path(__file__).parent / "data" / "audio"
ENGLISH = AUDIO / "jfk_inaugural_1961_en.ogg"
GERMAN = AUDIO / "goethe_grimm_espeak_de.ogg"


@pytest.fixture(scope="session")
def model_path():
    from faster_whisper import download_model
    cache = os.environ.get(
        "TSAPI_TEST_MODEL_DIR",
        str(Path(__file__).parent.parent / ".cache" / "models"))
    return download_model(os.environ.get("TSAPI_TEST_MODEL", "tiny"),
                          cache_dir=cache)


@pytest.fixture(autouse=True)
def real_model(monkeypatch, model_path):
    monkeypatch.setenv("whisper_model", model_path)
    monkeypatch.setenv("whisper_device", "cpu")
    monkeypatch.setenv("whisper_compute_type", "int8")
    monkeypatch.setenv("whisper_cpu_threads", "2")
    monkeypatch.setenv("transcription_timeout", "600")


def transcribe(audio: Path):
    ts_api = TsApi()
    entry = File.Entry(ts_api.file_module, "UID", 1)
    ts_api.database.add_job(entry)
    shutil.copy(audio, "./data/audioInput/UID")
    Transcriber(ts_api, entry).transcribe()
    job = ts_api.database.load_job("UID")
    assert job.status == JobStatus.COMPLETED, job.error_message
    return job


def text_of(job) -> str:
    return " ".join(segment["text"] for segment in job.whisper_result).lower()


class TestRealModel:

    def test_english(self):
        job = transcribe(ENGLISH)
        assert job.whisper_language == "en"
        text = text_of(job)
        assert "fellow americans" in text
        assert "your country" in text
        for segment in job.whisper_result:
            assert 0 <= segment["start"] < segment["end"] <= 11.5
            assert len(segment["text"]) <= 80
        assert job.vad_segments["segments"]
        assert not os.path.exists("./data/audioInput/UID")

    def test_german(self):
        job = transcribe(GERMAN)
        assert job.whisper_language == "de"
        text = text_of(job)
        words = ["gipfeln", "ruh", "hauch", "vögelein", "walde", "warte",
                 "mädchen", "vater", "mutter", "arm", "wohnen", "schlafen"]
        found = [word for word in words if word in text]
        assert len(found) >= 4, text

    def test_vad_skips_leading_silence(self):
        audio = Path("silence_and_speech.ogg")
        subprocess.run(
            ["ffmpeg", "-v", "error", "-f", "lavfi", "-t", "6",
             "-i", "anullsrc=r=16000:cl=mono", "-i", str(ENGLISH),
             "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1",
             "-c:a", "libopus", str(audio)],
            check=True)
        job = transcribe(audio)
        speech = job.vad_segments["segments"]
        assert speech[0]["start"] >= 5
        assert job.vad_segments["audio_duration"] == pytest.approx(17, 0.1)
        assert job.whisper_result[0]["start"] >= 5
        assert "fellow americans" in text_of(job)


AUTH = {"Authorization": "Basic "
        + base64.b64encode(b"username:password").decode()}


def test_api(monkeypatch):
    monkeypatch.setenv("login_username", "username")
    monkeypatch.setenv("login_password", "password")
    sys.modules.pop("app", None)
    app_module = importlib.import_module("app")
    try:
        client = app_module.app.test_client()
        with open(ENGLISH, "rb") as file:
            response = client.post("/transcribe", headers=AUTH, data={
                "priority": "1", "file": (file, "jfk.ogg")})
        assert response.status_code == 201
        job_id = response.json["jobId"]

        deadline = time.monotonic() + 600
        status = None
        while time.monotonic() < deadline:
            status = client.get(f"/status?id={job_id}",
                                headers=AUTH).json["status"]
            if status in ("Whispered", "Failed", "Canceled"):
                break
            time.sleep(1)
        assert status == "Whispered"

        srt = client.get(f"/transcribe?id={job_id}&format=srt",
                         headers=AUTH).data.decode()
        assert srt.startswith("1\n00:00:")
        assert "fellow americans" in srt.lower()
        assert client.get(f"/language?id={job_id}",
                          headers=AUTH).json["language"] == "en"
        assert client.get(f"/vad?id={job_id}&format=json", headers=AUTH
                          ).json["summary"]["segment_count"] >= 1
    finally:
        app_module.ts_api.running = False
        sys.modules.pop("app", None)
