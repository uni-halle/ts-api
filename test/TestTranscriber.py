import io
import os
import json

import pytest
from werkzeug.datastructures import FileStorage

from File import File
from core.Transcriber import Transcriber
from core.TsApi import TsApi


class TestTranscriber:
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
        pass
        if os.path.exists("./data/jobDatabase/UID.json"):
            os.remove("./data/jobDatabase/UID.json")

    def test_init(self):
        os.environ.setdefault("whisper_model", "small")
        ts_api: TsApi = TsApi()
        trans: Transcriber = Transcriber(ts_api, self.module_entry)
        assert trans.module_entry == self.module_entry
        assert trans.file_path == "./data/audioInput/UID"
        assert trans.whisper_result is None
        assert trans.whisper_language is None
        assert trans.ts_api == ts_api
