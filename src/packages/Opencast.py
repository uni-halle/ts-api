import logging
import uuid
import io
from abc import abstractmethod

from werkzeug.datastructures import FileStorage

import database
import util
import requests
from requests import request
from packages.Default import Default


class Opencast(Default):

    def __init__(self, max_queue_length):
        self.module_uid = str(uuid.uuid4())
        self.max_queue_length = max_queue_length
        self.entrys = {}
        logging.debug("Created Opencast Module with id " + self.module_uid +
                      ".")

    def create(self, uid, link, title):
        module_entry = Opencast.Entry(self, uid, link, title)
        self.entrys[uid] = module_entry
        return module_entry

    @abstractmethod
    class Entry:
        @abstractmethod
        def __init__(self, default, uid, link, title):
            self.default: Opencast = default
            self.uid = uid
            self.link = link
            self.initial_prompt = title
            logging.debug("Created Opencast Module entry with id " +
                          self.uid +
                          ".")

        @abstractmethod
        def queuing(self) -> bool:
            if len(self.default.entrys) < self.default.max_queue_length:
                database.add_job(self)
                return True
            return False

        @abstractmethod
        def preprocessing(self):
            logging.debug("Downloading file for job id " + self.uid + "...")
            session: request = requests.Session()
            response = session.get(self.link)
            if response.status_code != 200:
                raise Exception
            file = FileStorage(
                stream=io.BytesIO(response.content),
                filename=self.uid,
                content_length=response.headers.get("Content-Length"),
                content_type=response.headers.get("Content-Type")
            )
            util.save_file(file, self.uid)
            logging.debug("Downloaded file for job id " + self.uid + ".")
