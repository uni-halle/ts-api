import os.path
import pytest
import json
from queue import PriorityQueue

from Default import Default
from File import File
from utils import database


class TestDatabase:
    @pytest.fixture(autouse=True)
    def set_up_tear_down(self):
        if os.path.exists("./data/jobDatabase/UID.json"):
            os.remove("./data/jobDatabase/UID.json")
        self.module: File = File()
        self.module_entry: File.Entry = File.Entry(self.module, "UID", 1)
        job_data: str = json.dumps(self.module_entry, default=lambda o:
                                   o.__dict__)
        with open("./data/jobDatabase/" + self.module_entry.uid + ".json",
                  "x") as file:
            file.write(job_data)
            file.close()
        yield
        if os.path.exists("./data/queue.json"):
            os.remove("./data/queue.json")

    def test_add_job(self):
        if os.path.exists("./data/jobDatabase/UID.json"):
            os.remove("./data/jobDatabase/UID.json")
        database.add_job(self.module_entry)
        assert os.path.exists("./data/jobDatabase/UID.json")
        with open("./data/jobDatabase/UID.json", "r") as file:
            assert json.load(file) == {
                "priority": 1,
                "time": self.module_entry.time,
                "module": {
                    "module_type": self.module.module_type,
                    "module_uid": self.module.module_uid,
                    "entrys": self.module.entrys
                },
                "uid": "UID"
            }
            file.close()

    def test_load_job(self):
        job = database.load_job("UID")
        assert job == {
            "priority": self.module_entry.priority,
            "time": self.module_entry.time,
            "module":
                {
                    "module_type": self.module.module_type,
                    "module_uid": self.module.module_uid,
                    "entrys": self.module.entrys
                },
            "uid": self.module_entry.uid
        }

    def test_exists_job(self):
        assert database.exists_job("UID")

    def test_change_job_status(self):
        database.change_job_status(self.module_entry, 2)
        with open("./data/jobDatabase/UID.json", "r") as file:
            assert json.load(file)["status"] == 2
            file.close()

    def test_set_whisper_result(self):
        database.set_whisper_result(self.module_entry,
                                    {"result": "This should be subtitled."})
        with open("./data/jobDatabase/UID.json", "r") as file:
            assert json.load(file)["whisper_result"] == {
                "result": "This should be subtitled."
            }
            file.close()

    def test_set_whisper_language(self):
        database.set_whisper_language(self.module_entry, "Klingonisch")
        with open("./data/jobDatabase/UID.json", "r") as file:
            assert json.load(file)["whisper_language"] == "Klingonisch"
            file.close()

    def test_save_and_load_queue(self):
        queue: PriorityQueue[(int, Default.Entry)] = PriorityQueue()
        queue.put(("0", self.module_entry))
        database.save_queue(queue)
        assert os.path.exists("./data/queue.json")
        with open("./data/queue.json", "r") as file:
            second_queue = database.load_queue()
            assert second_queue.queue == queue.queue
            file.close()

    def test_load_queue_empty(self):
        queue = database.load_queue()
        queue_test = PriorityQueue()
        assert queue.queue == queue_test.queue
