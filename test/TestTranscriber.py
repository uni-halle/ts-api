import os
import json
import threading
import time
import types

import pytest

import core.Transcriber
import fake_worker
from packages.File import File
from core.Transcriber import Transcriber
from core.TsApi import TsApi
from utils.database import JobStatus


class TestTranscriber:
    @pytest.fixture(autouse=True)
    def set_up_tear_down(self):
        if os.path.exists("./data/jobDatabase/UID.json"):
            os.remove("./data/jobDatabase/UID.json")
        os.environ.setdefault("whisper_model", "small")
        self.ts_api: TsApi = TsApi()
        self.module: File = File()
        self.ts_api.database.add_module(self.module)
        self.module_entry: File.Entry = File.Entry(self.module, "UID", 1)
        self.ts_api.database.add_job(self.module_entry)
        job_data: str = json.dumps(self.module_entry, default=lambda o:
                                   o.__dict__)
        with open("./data/jobDatabase/" + self.module_entry.uid + ".json",
                  "x") as file:
            file.write(job_data)
            file.close()
        yield
        pass
        if os.path.exists("./data/jobDatabase/UID.json"):
            os.remove("./data/jobDatabase/UID.json")

    def test_init(self):
        os.environ.setdefault("whisper_model", "small")
        trans: Transcriber = Transcriber(self.ts_api, self.module_entry)
        assert trans.module_entry == self.module_entry
        assert trans.file_path == "./data/audioInput/UID"
        assert trans.whisper_result is None
        assert trans.whisper_language is None
        assert trans.ts_api == self.ts_api


class TestTranscriberProcess:
    """Runs the process handling with fake workers instead of Whisper"""

    @pytest.fixture(autouse=True)
    def set_up(self, monkeypatch):
        self.monkeypatch = monkeypatch
        self.ts_api: TsApi = TsApi()
        self.module_entry: File.Entry = File.Entry(self.ts_api.file_module,
                                                   "UID", 1)
        self.ts_api.database.add_job(self.module_entry)
        with open("./data/audioInput/UID", "w") as file:
            file.write("audio")

    def use_worker(self, function):
        self.monkeypatch.setattr(core.Transcriber, "whisper_worker",
                                 types.SimpleNamespace(run=function))

    def test_large_result(self):
        self.use_worker(fake_worker.large_result)
        Transcriber(self.ts_api, self.module_entry).transcribe()
        job = self.ts_api.database.load_job("UID")
        assert job.status == JobStatus.COMPLETED
        assert len(job.whisper_result) == 20000
        assert job.whisper_language == "de"
        assert job.vad_segments["audio_duration"] == 2
        assert not os.path.exists("./data/audioInput/UID")

    def test_error(self):
        self.use_worker(fake_worker.error)
        Transcriber(self.ts_api, self.module_entry).transcribe()
        job = self.ts_api.database.load_job("UID")
        assert job.status == JobStatus.FAILED
        assert "broken" in job.error_message

    def test_crash(self):
        self.use_worker(fake_worker.crash)
        Transcriber(self.ts_api, self.module_entry).transcribe()
        job = self.ts_api.database.load_job("UID")
        assert job.status == JobStatus.FAILED
        assert "exit code 3" in job.error_message

    def test_cancel(self):
        self.use_worker(fake_worker.hang)
        event = threading.Event()
        transcriber = Transcriber(self.ts_api, self.module_entry, event)
        threading.Timer(1, event.set).start()
        start = time.monotonic()
        transcriber.transcribe()
        assert time.monotonic() - start < 15
        assert not transcriber.transcription_process.is_alive()
        job = self.ts_api.database.load_job("UID")
        assert job.status == JobStatus.CANCELED

    def test_timeout(self):
        self.use_worker(fake_worker.hang)
        self.monkeypatch.setenv("transcription_timeout", "1")
        transcriber = Transcriber(self.ts_api, self.module_entry)
        transcriber.transcribe()
        assert not transcriber.transcription_process.is_alive()
        job = self.ts_api.database.load_job("UID")
        assert job.status == JobStatus.FAILED
        assert "not finished" in job.error_message
