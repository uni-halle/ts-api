import os.path
import pytest
import json
from queue import PriorityQueue

from utils import database


def setUpFile() -> None:
    job_data = {"id": 1,
                "filename": "1.txt",
                "status": 0}
    with open("./data/jobDatabase/1.json", "x") as file:
        file.write(json.dumps(job_data))
        file.close()


class TestDatabase:
    @pytest.fixture(autouse=True)
    def set_up_tear_down(self):
        yield
        if os.path.exists("./data/jobDatabase/1.json"):
            os.remove("./data/jobDatabase/1.json")
        if os.path.exists("./data/jobDatabase/queue.json"):
            os.remove("./data/jobDatabase/queue.json")

    def test_add_job(self):
        database.add_job("Testfile.txt", "1")
        assert os.path.exists("./data/jobDatabase/1.json")
        with open("./data/jobDatabase/1.json", "r") as file:
            assert json.load(file) == {"filename": "1.txt", "id": "1", "status": 0}
            file.close()

    def test_load_job(self):
        setUpFile()
        assert database.load_job("1") == {"filename": "1.txt", "id": 1, "status": 0}

    def test_exists_job(self):
        setUpFile()
        assert database.exists_job("1")

    def test_change_job_status(self):
        setUpFile()
        database.change_job_status("1", 2)
        with open("./data/jobDatabase/1.json", "r") as file:
            assert json.load(file) == {"filename": "1.txt", "id": 1, "status": 2}
            file.close()

    def test_set_whisper_result(self):
        setUpFile()
        database.set_whisper_result("1", {"result": "This should be subtitled."})
        with open("./data/jobDatabase/1.json", "r") as file:
            assert json.load(file)["whisper_result"] == {"result": "This should be subtitled."}
            file.close()

    def test_set_whisper_language(self):
        setUpFile()
        database.set_whisper_language("1", "Klingonisch")
        with open("./data/jobDatabase/1.json", "r") as file:
            assert json.load(file)["whisper_language"] == "Klingonisch"
            file.close()

    def test_save_queue(self):
        queue = PriorityQueue()
        queue.put(("0", "1"))
        database.save_queue(queue)
        assert os.path.exists("./data/jobDatabase/queue.json")
        with open("./data/jobDatabase/queue.json", "r") as file:
            assert json.load(file) == [['0', '1']]
            file.close()

    def test_load_queue_existing(self):
        queue_insert = PriorityQueue()
        queue_insert.put(("0", "1"))
        with open("./data/jobDatabase/queue.json", "x") as file:
            file.write(json.dumps(queue_insert.queue))
            file.close()
        queue = database.load_queue()
        queue_test = PriorityQueue()
        queue_test.put(("0", "1"))
        assert queue.queue == queue_test.queue

    def test_load_queue_empty(self):
        queue = database.load_queue()
        queue_test = PriorityQueue()
        assert queue.queue == queue_test.queue
