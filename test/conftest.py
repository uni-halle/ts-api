import os

import pytest

# Never download Whisper models in tests
os.environ["whisper_preload_model"] = "false"
os.environ.setdefault("whisper_model", "small")


@pytest.fixture(autouse=True)
def data_directory(tmp_path, monkeypatch):
    """Run every test in an empty working directory with the data folders"""
    for folder in ("audioInput", "jobDatabase", "models", "moduleDatabase"):
        (tmp_path / "data" / folder).mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    yield tmp_path
