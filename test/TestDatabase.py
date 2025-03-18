import os.path
import pytest
import json
from queue import PriorityQueue

from Default import Default
from File import File
from utils.database import Database


class TestDatabase:
    @pytest.fixture(autouse=True)
    def set_up_tear_down(self):
        self.database = Database()
        self.module: File = File()
        self.database.add_module(self.module)
        self.module_entry: File.Entry = File.Entry(self.module, "UID", 1)
        self.database.add_job(self.module_entry)
        yield
        if os.path.exists("./data/queue.json"):
            os.remove("./data/queue.json")
        if os.path.exists("./data/audioInput/UID"):
            os.remove("./data/audioInput/UID")

    def test_add_job(self):
        self.database.add_job(self.module_entry)
        assert self.database.load_job(self.module_entry.uid) == self.module_entry

    def test_load_job(self):
        job = self.database.load_job("UID")
        assert job == self.module_entry

    def test_exists_job(self):
        assert self.database.exists_job("UID")

    def test_change_job_status(self):
        self.database.change_job_entry(self.module_entry.uid, "status", 2)
        assert self.database.load_job(self.module_entry.uid).status == 2

    def test_set_whisper_result(self):
        self.database.change_job_entry(self.module_entry.uid, "whisper_result",
                                    {"result": "This should be subtitled."})
        assert self.database.load_job(self.module_entry.uid).whisper_result == {"result": "This should be subtitled."}

    def test_set_whisper_language(self):
        self.database.change_job_entry(self.module_entry.uid,
                                       "whisper_language", "Klingonisch")
        assert self.database.load_job(
            self.module_entry.uid).whisper_language == "Klingonisch"

