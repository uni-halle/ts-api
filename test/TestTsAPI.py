import os

from core.TsApi import TsApi


class TestTsAPI:

    def test_init(self):
        os.environ.setdefault("whisper_model", "small")
        ts_api: TsApi = TsApi()
        assert ts_api.running
        assert len(ts_api.running_jobs) == 0
        assert ts_api.file_module is not None


class TestModelInfo:
    def test_model_name(self):
        assert TsApi.model_name("large-v3") == "large-v3"
        assert TsApi.model_name("/models/large-v3/") == "large-v3"
        name = TsApi.model_name
        assert name("Systran/faster-whisper-large-v3") == "large-v3"
        assert name("org/faster-whisper-large-v3-turbo") == "large-v3-turbo"

    def test_resolve_device(self):
        assert TsApi.resolve_device("cpu") == "cpu"
        assert TsApi.resolve_device(" CUDA ") == "cuda"
        assert TsApi.resolve_device("auto") in ("cpu", "cuda")
        assert TsApi.resolve_device("") in ("cpu", "cuda")
