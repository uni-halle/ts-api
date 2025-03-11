import os

from core.TsApi import TsApi


class TestTsAPI:

    def test_init(self):
        os.environ.setdefault("whisper_model", "small")
        ts_api: TsApi = TsApi()
        assert ts_api.running
        assert len(ts_api.running_jobs) == 0
        assert ts_api.modules is not None
        assert ts_api.queue is not None
        assert ts_api.file_module is not None
