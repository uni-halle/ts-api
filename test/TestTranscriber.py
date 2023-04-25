import io
import os
import json

import pytest
from werkzeug.datastructures import FileStorage

from core.Transcriber import Transcriber
from core.TsApi import TsApi


class TestTranscriber:
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

    def test_init(self):
        ts_api: TsApi = TsApi()
        trans: Transcriber = Transcriber(ts_api, "1")
        assert trans.uid == "1"
        assert trans.file_path == "./data/audioInput/1.txt"
        assert trans.whisper_result is None
        assert trans.whisper_language is None
        assert trans.ts_api == ts_api
