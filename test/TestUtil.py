import io
import json
import os.path
import pytest

from werkzeug.datastructures import FileStorage
from utils import util


class TestUtil:
    @pytest.fixture(autouse=True)
    def set_up_tear_down(self):
        yield
        if os.path.exists("./data/audioInput/1.txt"):
            os.remove("./data/audioInput/1.txt")

    def test_save_file(self):
        file = FileStorage(
            stream=io.BytesIO(bytes("Test", 'UTF-8')),
            filename="1.txt"
        )
        util.save_file(file, "1")
        with open("./data/audioInput/1.txt", "r") as file:
            assert file.read() == "Test"
            file.close()

    def test_get_status(self):
        status = {
            0: "Prepared",
            1: "Running",
            2: "Whispered",
            3: "Failed"
        }
        for i in range(4):
            assert util.get_status(i) == status.get(i, 'Error')