import io
import os
import json
import pytest

from werkzeug.datastructures import FileStorage

from core.TsApi import TsApi


class TestTsAPI:
    @pytest.fixture(autouse=True)
    def set_up_tear_down(self):
        job_data = {"id": "UID",
                    "module_id": None,
                    "status": 0}
        with open("./data/jobDatabase/UID.json", "x") as file:
            file.write(json.dumps(job_data))
            file.close()
        file = FileStorage(
            stream=io.BytesIO(bytes("Test", 'UTF-8')),
            filename="1.txt"
        )
        file.save("./data/audioInput/UID")
        yield
        if os.path.exists("./data/jobDatabase/UID.json"):
            os.remove("./data/jobDatabase/UID.json")
        if os.path.exists("./data/audioInput/UID.txt"):
            os.remove("./data/audioInput/UID.txt")
        if os.path.exists("./data/jobDatabase/UID_2.json"):
            os.remove("./data/jobDatabase/UID_2.json")
        if os.path.exists("./data/audioInput/UID_2"):
            os.remove("./data/audioInput/UID_2")

    def test_init(self):
        os.environ.setdefault("whisper_model", "small")
        ts_api: TsApi = TsApi()
        assert ts_api.running
        assert len(ts_api.runningJobs) == 0

    def test_register_job(self):
        ts_api: TsApi = TsApi()
        ts_api.register_job("UID", None)
        assert len(ts_api.runningJobs) == 1
        assert ts_api.runningJobs.pop(0) == "UID"

    def test_unregister_job(self):
        ts_api: TsApi = TsApi()
        ts_api.runningJobs.append("UID")
        ts_api.unregister_job("UID")
        assert len(ts_api.runningJobs) == 0
