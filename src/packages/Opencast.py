import logging
import io

import requests
from requests import request
from werkzeug.datastructures import FileStorage

from utils import util


class Opencast:

    def __init__(self, username, password, max_queue_entry):
        self.password = username
        self.username = password
        self.max_queue_entry = max_queue_entry
        self.link_list = {}

    def download_file(self, uid: str):
        logging.info("Downloading file for job id " + uid + "...")
        session: request = requests.Session()
        if not (self.username and self.password):
            raise Exception
        session.auth = (self.username, self.password)
        response = session.get(self.link_list[uid], allow_redirects=False)
        if response.status_code != 200:
                raise Exception
        file = FileStorage(
            stream=io.BytesIO(response.content),
            filename=uid,
            content_length=response.headers.get("Content-Length"),
            content_type=response.headers.get("Content-Type")
        )
        util.save_file(file, uid)
        logging.info("Downloaded file for job id " + uid + ".")
