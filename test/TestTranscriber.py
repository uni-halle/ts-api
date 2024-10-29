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
        job_data = {"id": "UID",
                    "module_id": None,
                    "status": 0}
        with open("./data/jobDatabase/UID.json", "x") as file:
            file.write(json.dumps(job_data))
            file.close()
        file = FileStorage(
            stream=io.BytesIO(bytes("Test", 'UTF-8')),
            filename="UID"
        )
        file.save("./data/audioInput/UID")
        yield
        if os.path.exists("./data/jobDatabase/UID.json"):
            os.remove("./data/jobDatabase/UID.json")
        if os.path.exists("./data/audioInput/UID"):
            os.remove("./data/audioInput/UID")

    def test_init(self):
        os.environ.setdefault("whisper_model", "small")
        ts_api: TsApi = TsApi()
        trans: Transcriber = Transcriber(ts_api, "UID")
        assert trans.uid == "UID"
        assert trans.file_path == "./data/audioInput/UID"
        assert trans.whisper_result is None
        assert trans.whisper_language is None
        assert trans.ts_api == ts_api
