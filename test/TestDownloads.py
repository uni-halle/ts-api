import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import core.TsApi
from core.TsApi import TsApi
from packages.Default import JobCanceled
from packages.Opencast import Opencast
from utils.database import JobStatus


class LocalServer:
    """HTTP server on localhost, the tests never access other hosts"""

    def __init__(self):
        self.lock = threading.Lock()
        self.active = 0
        self.max_active = 0
        self.requests = {}
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                with server.lock:
                    server.active += 1
                    server.max_active = max(server.max_active, server.active)
                    server.requests[self.path] = \
                        server.requests.get(self.path, 0) + 1
                try:
                    self.respond()
                finally:
                    with server.lock:
                        server.active -= 1

            def respond(self):
                if self.path.startswith("/slow"):
                    time.sleep(1)
                if self.path.startswith("/missing"):
                    self.send_response(404)
                    self.end_headers()
                    return
                if self.path.startswith("/error"):
                    self.send_response(500)
                    self.end_headers()
                    return
                body = b"audio" * 1000
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if self.path.startswith("/hang"):
                    # Headers sent, body never arrives
                    self.wfile.write(body[:10])
                    self.wfile.flush()
                    time.sleep(5)
                    return
                self.wfile.write(body)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever,
                                       daemon=True)
        self.thread.start()

    def url(self, path):
        return f"http://127.0.0.1:{self.httpd.server_port}{path}"

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setenv("download_read_timeout", "2")
    monkeypatch.setenv("download_retries", "0")
    local_server = LocalServer()
    yield local_server
    local_server.close()


class FakeTranscriber:
    """Marks the job as transcribed without running Whisper"""

    def __init__(self, ts_api, module_entry, cancel_event=None):
        self.ts_api = ts_api
        self.module_entry = module_entry

    def transcribe(self):
        self.ts_api.database.update_job_status(self.module_entry.uid,
                                               JobStatus.COMPLETED,
                                               whisper_result=[])


def wait_for(condition, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.05)
    return False


def audio_path(uid):
    return os.path.join("data", "audioInput", uid)


class TestDownload:

    def entry(self, link, uid="UID"):
        return Opencast.Entry(Opencast(max_queue_length=10), uid, link)

    def test_download(self, server):
        self.entry(server.url("/ok")).preprocessing()
        with open(audio_path("UID"), "rb") as file:
            assert file.read() == b"audio" * 1000
        assert not os.path.exists(audio_path("UID") + ".part")

    def test_not_found(self, server):
        with pytest.raises(Exception, match="HTTP 404"):
            self.entry(server.url("/missing")).preprocessing()
        assert not os.path.exists(audio_path("UID"))
        assert not os.path.exists(audio_path("UID") + ".part")

    def test_server_error_is_retried(self, server, monkeypatch):
        monkeypatch.setenv("download_retries", "1")
        with pytest.raises(Exception, match="HTTP 500"):
            self.entry(server.url("/error")).preprocessing()
        assert server.requests["/error"] == 2

    def test_stalled_download_times_out(self, server, monkeypatch):
        monkeypatch.setenv("download_read_timeout", "0.5")
        start = time.monotonic()
        with pytest.raises(Exception, match="Failed to download"):
            self.entry(server.url("/hang")).preprocessing()
        assert time.monotonic() - start < 4
        assert not os.path.exists(audio_path("UID"))
        assert not os.path.exists(audio_path("UID") + ".part")

    def test_cancel(self, server):
        event = threading.Event()
        event.set()
        with pytest.raises(JobCanceled):
            self.entry(server.url("/ok")).preprocessing(event)
        assert not os.path.exists(audio_path("UID"))


class TestPipeline:

    @pytest.fixture(autouse=True)
    def set_up(self, server, monkeypatch):
        monkeypatch.setattr(core.TsApi, "Transcriber", FakeTranscriber)
        monkeypatch.setenv("parallel_downloads", "3")
        self.server = server
        self.ts_api = TsApi()
        self.module = Opencast(max_queue_length=10)
        self.ts_api.database.add_module(self.module)
        yield
        self.ts_api.running = False

    def queue(self, uid, path):
        entry = Opencast.Entry(self.module, uid, self.server.url(path))
        assert entry.queuing(self.ts_api)
        return entry

    def status(self, uid):
        return self.ts_api.database.load_job(uid).status

    def test_parallel_downloads_and_failures(self):
        self.queue("broken", "/missing")
        self.queue("hanging", "/hang")
        for i in range(3):
            self.queue(f"job{i}", f"/slow{i}")
        start = time.monotonic()
        self.ts_api.start_thread()

        assert wait_for(lambda: all(
            self.status(f"job{i}") == JobStatus.COMPLETED for i in range(3)))
        assert wait_for(lambda: self.status("hanging") == JobStatus.CANCELED)
        assert self.status("broken") == JobStatus.CANCELED
        assert "404" in self.ts_api.database.load_job("broken").error_message
        # The slow downloads ran in parallel
        assert self.server.max_active >= 2
        assert time.monotonic() - start < 10
        assert wait_for(lambda: self.module.queued_or_active == 0)
        assert self.ts_api.queue_length == 0
        assert self.ts_api.database.get_stats()["queue_length"] == 0

    def test_delete_during_download(self, monkeypatch):
        monkeypatch.setenv("download_read_timeout", "30")
        self.queue("hanging", "/hang")
        self.ts_api.start_thread()
        assert wait_for(lambda: len(self.ts_api.downloading_jobs) == 1)
        assert self.ts_api.delete_job("hanging")
        assert not self.ts_api.database.exists_job("hanging")
        assert wait_for(lambda: len(self.ts_api.downloading_jobs) == 0,
                        timeout=5)
        assert self.module.queued_or_active == 0
        assert not os.path.exists(audio_path("hanging"))

    def test_delete_queued_job(self):
        self.queue("queued", "/ok")
        assert self.ts_api.delete_job("queued")
        assert self.module.queued_or_active == 0
        self.ts_api.start_thread()
        time.sleep(1.5)
        assert self.server.requests.get("/ok") is None
        assert not self.ts_api.delete_job("queued")

    def test_restart_restores_queue(self):
        self.queue("queued", "/ok")
        restarted = TsApi()
        entry = restarted.database.load_job("queued")
        assert entry.link == self.server.url("/ok")
        assert entry.module.max_queue_length == 10
        assert entry.module.queued_or_active == 1
        assert restarted.queue_length == 1
