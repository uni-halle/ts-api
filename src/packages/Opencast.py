import logging
import io

import requests
from requests import request
from werkzeug.datastructures import FileStorage

from utils import util


class Opencast:

    def __init__(self, max_queue_entry, uid, queue_entry=0, link_list=None):
        if link_list is None:
            link_list = {}
        logging.debug("Created Opencast Module with id " + uid + ".")
        self.uid = uid
        self.max_queue_entry = max_queue_entry
        self.queue_entry = queue_entry
        self.link_list = link_list

    def download_file(self, uid: str):
        logging.info("Downloading file for job id " + uid + "...")
        session: request = requests.Session()
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
        self.link_list.pop(uid)
        logging.info("Downloaded file for job id " + uid + ".")
