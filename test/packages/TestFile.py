import io
import os.path

import pytest
from werkzeug.datastructures import FileStorage

from core.TsApi import TsApi
from packages.File import File


class TestUtil:
    @pytest.fixture(autouse=True)
    def set_up_tear_down(self):
        os.environ.setdefault("whisper_model", "small")
        self.ts_api: TsApi = TsApi()
        self.file: FileStorage = FileStorage(
            stream=io.BytesIO(bytes("Test", 'UTF-8')),
            filename="UID"
        )
        yield
        if os.path.exists("./data/jobDatabase/UID.json"):
            os.remove("./data/jobDatabase/UID.json")

    def test_module_creation(self):
        module: File = File()
        assert module.module_uid is not None
        assert module.queued_or_active is not None

    def test_entry_creation(self):
        module: File = File()
        module_entry: File.Entry = File.Entry(module=module, uid="UID",
                                              priority=1)
        assert module_entry.queuing(self.ts_api, self.file) is True
        assert module_entry.module is not None
        assert module_entry.uid is not None
        assert module_entry.time is not None
