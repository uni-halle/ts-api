import io
import os
import json
import pytest

from werkzeug.datastructures import FileStorage

from core.TsApi import TsApi


class TestTsAPI:
    @pytest.fixture(autouse=True)
    def set_up_tear_down(self):
        job_data = {"id": 1,
                    "filename": "1.txt",
                    "status": 0}
        with open("./data/jobDatabase/1.json", "x") as file:
            file.write(json.dumps(job_data))
            file.close()
        file = FileStorage(
            stream=io.BytesIO(bytes("Test", 'UTF-8')),
            filename="1.txt"
        )
        file.save("./data/audioInput/1.txt")
        yield
        if os.path.exists("./data/jobDatabase/1.json"):
            os.remove("./data/jobDatabase/1.json")
        if os.path.exists("./data/audioInput/1.txt"):
            os.remove("./data/audioInput/1.txt")
        if os.path.exists("./data/jobDatabase/2.json"):
            os.remove("./data/jobDatabase/2.json")
        if os.path.exists("./data/audioInput/2.txt"):
            os.remove("./data/audioInput/2.txt")

    def test_init(self):
        ts_api: TsApi = TsApi()
        assert ts_api.running
        assert len(ts_api.runningJobs) == 0
        assert len(ts_api.runningDownloads) == 0

    def test_add_file_to_queue(self):
        ts_api: TsApi = TsApi()
        file = FileStorage(
            stream=io.BytesIO(bytes("Test", 'UTF-8')),
            filename="2.txt"
        )
        ts_api.add_file_to_queue("2", file, 1)
        assert ts_api.queue.get() == (1, "2")

    def test_register_job(self):
        ts_api: TsApi = TsApi()
        ts_api.register_job("1")
        assert len(ts_api.runningJobs) == 1
        assert ts_api.runningJobs.pop(0) == "1"

    def test_unregister_job(self):
        ts_api: TsApi = TsApi()
        ts_api.runningJobs.append("1")
        ts_api.unregister_job("1")
        assert len(ts_api.runningJobs) == 0
