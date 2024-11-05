import os.path
import pytest
import json
from queue import PriorityQueue

from utils import database


def set_up_file() -> None:
    job_data = {"id": "UID",
                "module_id": None,
                "status": 0}
    with open("./data/jobDatabase/UID.json", "x") as file:
        file.write(json.dumps(job_data))
        file.close()


class TestDatabase:
    @pytest.fixture(autouse=True)
    def set_up_tear_down(self):
        yield
        if os.path.exists("./data/jobDatabase/UID.json"):
            os.remove("./data/jobDatabase/UID.json")
        if os.path.exists("./data/jobDatabase/queue.json"):
            os.remove("./data/jobDatabase/queue.json")

    def test_add_job(self):
        database.add_job("UID", None)
        assert os.path.exists("./data/jobDatabase/UID.json")
        with open("./data/jobDatabase/UID.json", "r") as file:
            assert json.load(file) == {
                "id": "UID",
                "module_id": None,
                "status": 0
            }
            file.close()

    def test_load_job(self):
        set_up_file()
        assert database.load_job("UID") == {
            "id": "UID",
            "module_id": None,
            "status": 0
        }

    def test_exists_job(self):
        set_up_file()
        assert database.exists_job("UID")

    def test_change_job_status(self):
        set_up_file()
        database.change_job_status("UID", 2)
        with open("./data/jobDatabase/UID.json", "r") as file:
            assert json.load(file) == {
                "id": "UID",
                "module_id": None,
                "status": 2
            }
            file.close()

    def test_set_whisper_result(self):
        set_up_file()
        database.set_whisper_result("UID",
                                    {"result": "This should be subtitled."})
        with open("./data/jobDatabase/UID.json", "r") as file:
            assert json.load(file)["whisper_result"] == {
                "result": "This should be subtitled."
            }
            file.close()

    def test_set_whisper_language(self):
        set_up_file()
        database.set_whisper_language("UID", "Klingonisch")
        with open("./data/jobDatabase/UID.json", "r") as file:
            assert json.load(file)["whisper_language"] == "Klingonisch"
            file.close()

    def test_save_queue(self):
        queue = PriorityQueue()
        queue.put(("0", "UID"))
        database.save_queue(queue)
        assert os.path.exists("./data/jobDatabase/queue.json")
        with open("./data/jobDatabase/queue.json", "r") as file:
            assert json.load(file) == [['0', 'UID']]
            file.close()

    def test_load_queue_existing(self):
        queue_insert = PriorityQueue()
        queue_insert.put(("0", "UID"))
        with open("./data/jobDatabase/queue.json", "x") as file:
            file.write(json.dumps(queue_insert.queue))
            file.close()
        queue = database.load_queue()
        queue_test = PriorityQueue()
        queue_test.put(("0", "UID"))
        assert queue.queue == queue_test.queue

    def test_load_queue_empty(self):
        queue = database.load_queue()
        queue_test = PriorityQueue()
        assert queue.queue == queue_test.queue
