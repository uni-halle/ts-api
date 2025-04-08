import io
import os.path
import pytest

from werkzeug.datastructures import FileStorage
from utils import util


class TestUtil:
    @pytest.fixture(autouse=True)
    def set_up_tear_down(self):
        yield
        if os.path.exists("data/audioInput/UID"):
            os.remove("data/audioInput/UID")

    def test_save_file(self):
        file = FileStorage(
            stream=io.BytesIO(bytes("Test", 'UTF-8')),
            filename="UID"
        )
        util.save_file(file, "UID")
        with open("./data/audioInput/UID", "r") as file:
            assert file.read() == "Test"
            file.close()

    def test_get_status(self):
        status = {
            0: "Queued",
            1: "Prepared",
            2: "Processed",
            3: "Whispered",
            4: "Failed",
            5: "Canceled"
        }
        for i in range(5):
            assert util.get_status(i) == status.get(i, 'error')
