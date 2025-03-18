import os.path
import pytest

from core.TsApi import TsApi
from packages.Opencast import Opencast


class TestUtil:
    @pytest.fixture(autouse=True)
    def set_up_tear_down(self):
        os.environ.setdefault("whisper_model", "small")
        self.ts_api: TsApi = TsApi()
        yield
        if os.path.exists("./data/jobDatabase/UID.json"):
            os.remove("./data/jobDatabase/UID.json")

    def test_module_creation(self):
        module: Opencast = Opencast(max_queue_length=2)
        assert module.module_uid is not None
        assert module.entrys is not None
        assert module.max_queue_length == 2

    def test_entry_creation(self):
        module: Opencast = Opencast(max_queue_length=2)
        module_entry: Opencast.Entry = Opencast.Entry(module=module,
                                                      uid="UID", link="link",
                                                      initial_prompt="Test")
        assert module_entry.queuing(self.ts_api) is True
        assert module_entry.module is not None
        assert module_entry.uid is not None
        assert module_entry.time is not None
        assert module_entry.link is not None
        assert module_entry.initial_prompt is not None
