import base64
import importlib
import io
import sys
import time

import pytest

import core.TsApi
from utils.database import JobStatus


class FakeTranscriber:
    """Produces a fixed transcript without running Whisper"""

    def __init__(self, ts_api, module_entry, cancel_event=None):
        self.ts_api = ts_api
        self.module_entry = module_entry

    def transcribe(self):
        uid = self.module_entry.uid
        self.ts_api.database.change_job_entry(uid, "whisper_language", "de")
        self.ts_api.database.change_job_entry(
            uid, "vad_segments",
            {"segments": [{"start": 0.5, "end": 1.5}], "audio_duration": 2})
        self.ts_api.database.update_job_status(
            uid, JobStatus.COMPLETED,
            whisper_result=[{"start": 0.5, "end": 1.5, "text": " Hallo"}])


AUTH = {"Authorization": "Basic "
        + base64.b64encode(b"username:password").decode()}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("login_username", "username")
    monkeypatch.setenv("login_password", "password")
    monkeypatch.setenv("download_retries", "0")
    monkeypatch.setattr(core.TsApi, "Transcriber", FakeTranscriber)
    sys.modules.pop("app", None)
    app_module = importlib.import_module("app")
    yield app_module.app.test_client()
    app_module.ts_api.running = False
    sys.modules.pop("app", None)


def wait_for_status(client, job_id, status, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/status?id={job_id}", headers=AUTH)
        if response.json["status"] == status:
            return True
        time.sleep(0.1)
    return False


def test_refuses_to_start_without_credentials(monkeypatch):
    monkeypatch.delenv("login_username", raising=False)
    monkeypatch.setenv("login_password", "password")
    sys.modules.pop("app", None)
    with pytest.raises(RuntimeError, match="login_username"):
        importlib.import_module("app")
    sys.modules.pop("app", None)


class TestApp:

    def test_authorisation(self, client):
        assert client.get("/").status_code == 401
        assert client.get("/", headers={
            "Authorization": "Basic "
            + base64.b64encode(b"username:wrong").decode()
        }).status_code == 401
        assert client.get("/", headers=AUTH).status_code == 200

    def test_file_job(self, client):
        response = client.post("/transcribe", headers=AUTH, data={
            "priority": "1",
            "file": (io.BytesIO(b"audio"), "audio.mp3"),
        })
        assert response.status_code == 201
        job_id = response.json["jobId"]
        assert wait_for_status(client, job_id, "Whispered")

        response = client.get(f"/transcribe?id={job_id}&format=srt",
                              headers=AUTH)
        assert response.status_code == 200
        assert response.mimetype == "application/x-subrip"
        assert response.data.decode() == \
            "1\n00:00:00,500 --> 00:00:01,500\nHallo\n"
        response = client.get(f"/transcribe?id={job_id}&format=json",
                              headers=AUTH)
        assert response.json == [{"start": 0.5, "end": 1.5, "text": "Hallo"}]
        assert client.get(f"/language?id={job_id}",
                          headers=AUTH).json["language"] == "de"
        assert client.get(f"/vad?id={job_id}&format=json",
                          headers=AUTH).json["summary"]["segment_count"] == 1

        assert client.delete(f"/transcribe?id={job_id}",
                             headers=AUTH).status_code == 200
        assert client.get(f"/status?id={job_id}",
                          headers=AUTH).status_code == 404

    def test_opencast_module(self, client):
        response = client.post("/module/opencast", headers=AUTH,
                               data={"max_queue_length": "1"})
        assert response.status_code == 201
        module_id = response.json["moduleId"]
        other = client.post("/module/opencast", headers=AUTH,
                            data={"max_queue_length": "1"})
        assert other.json["moduleId"] != module_id

        # Unreachable local port, the download fails quickly
        data = {"priority": "1", "module": "opencast",
                "module_id": module_id, "link": "http://127.0.0.1:9/x"}
        response = client.post("/transcribe", headers=AUTH, data=data)
        assert response.status_code == 201
        job_id = response.json["jobId"]
        assert wait_for_status(client, job_id, "Canceled")
        assert "error" in client.get(f"/status?id={job_id}",
                                     headers=AUTH).json

    def test_forbidden_link(self, client, monkeypatch):
        monkeypatch.setenv("allowed_download_hosts", "opencast.example.org")
        module_id = client.post("/module/opencast", headers=AUTH, data={
            "max_queue_length": "1"}).json["moduleId"]
        for link in ("http://127.0.0.1:9/x", "ftp://opencast.example.org/x"):
            response = client.post("/transcribe", headers=AUTH, data={
                "priority": "1", "module": "opencast",
                "module_id": module_id, "link": link})
            assert response.status_code == 400
            assert "allowed" in response.json["error"]

    def test_system_status(self, client):
        response = client.get("/status/system", headers=AUTH)
        assert response.status_code == 200
        assert response.json["queue_length"] == 0
        assert response.json["running_downloads"] == 0
