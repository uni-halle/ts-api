import logging
import uuid

from abc import abstractmethod, abstractclassmethod

from flake8.formatting.default import Default

import database
import util


class Default:

    @abstractmethod
    def __init__(self):
        self.module_uid = str(uuid.uuid4())
        self.entrys = {}
        logging.debug("Created Default Module with id " + self.module_uid +
                      ".")

    def create(self, uid):
        module_entry = Default.Entry(self, uid)
        self.entrys[uid] = module_entry
        return module_entry

    @abstractmethod
    class Entry:
        @abstractmethod
        def __init__(self, default, uid):
            self.default = default
            self.uid = uid
            logging.debug("Created Default Module entry with id " +
                          self.uid +
                          ".")

        @abstractmethod
        def queuing(self, file):
            util.save_file(file, self.uid)
            database.add_job(self)

        @abstractmethod
        def preprocessing(self):
            pass
