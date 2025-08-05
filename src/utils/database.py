import json
import logging
import os
import numpy as np

from pydoc import locate

from queue import PriorityQueue
from typing import Dict

from packages.Default import Default


class Database:
    modules: [str, Default] = {}
    module_entrys: [str, Default.Entry] = {}
    queue: PriorityQueue[(int, Default.Entry)] = PriorityQueue()

    def __init__(self):
        # Load Modules
        logging.debug("Loading Modules from database.")
        modules: Dict[str, Default] = {}
        for file_name in os.listdir("./data/moduleDatabase"):
            if file_name.endswith(".json"):
                file_path = os.path.join("./data/moduleDatabase", file_name)
                with open(file_path, "r", encoding="utf-8") as file:
                    module_data_raw = json.load(file)
                    module_type: object = locate("packages." + module_data_raw[
                        "module_type"])
                    module: module_type = module_type(**module_data_raw)
                    modules[module.module_uid] = module
        self.modules = modules
        # Load Module Entrys
        module_entrys: Dict[str, Default.Entry] = {}
        for file_name in os.listdir("./data/jobDatabase"):
            if file_name.endswith(".json"):
                file_path = os.path.join("./data/jobDatabase", file_name)
                with open(file_path, "r", encoding="utf-8") as file:
                    # Rebuild module_entry
                    module_entry_data_raw = json.load(file)
                    module_entry_type: object = locate("packages."
                                                       + module_entry_data_raw[
                                                           "module"][
                                                           "module_type"]
                                                       + ".Entry")
                    # Find module and insert link
                    module_type: object = locate("packages."
                                                 + module_entry_data_raw[
                                                     "module"]["module_type"])
                    module: module_type = self.modules.get(
                        module_entry_data_raw["module"]["module_uid"])
                    module_entry_data_raw["module"] = module
                    # Insert module_entry
                    module_entry: module_entry_type = module_entry_type(
                        **module_entry_data_raw)
                    module_entrys[module_entry.uid] = module_entry
        self.module_entrys = module_entrys
        # Load Queue
        logging.debug("Loading queue from database.")
        queue: PriorityQueue[(int, Default.Entry)] = PriorityQueue()
        if os.path.exists("./data/queue.json"):
            with (open("./data/queue.json", "r") as file):
                queue_data = json.load(file)
                while len(queue_data) > 0:
                    priority, module_entry_data_raw = queue_data.pop()
                    # Find module_entry and insert
                    module_entry_type: object = locate("packages."
                                                       + module_entry_data_raw[
                                                           "module"][
                                                           "module_type"]
                                                       + ".Entry")
                    module_entry: module_entry_type = self.module_entrys.get(
                        module_entry_data_raw["uid"])
                    # Rebuild queue
                    queue.put((priority, module_entry))
        self.queue = queue

    def save_database(self) -> bool:
        """
        Saves the given database to the storage
        :return: Nothing
        """

        def safe_serialize(o):
            if hasattr(o, '__dict__'):
                return o.__dict__
            elif isinstance(o, (np.float32, np.float64)):
                return float(o)
            elif isinstance(o, (np.int32, np.int64)):
                return int(o)
            elif isinstance(o, np.ndarray):
                return o.tolist()
            else:
                return str(o)

        # Safe Modules
        try:
            logging.debug("Saving modules to database.")
            for uid, module in self.modules.items():
                if module.queued_or_active == 0:
                    if os.path.exists("./data/moduleDatabase/"
                                      + uid + ".json"):
                        os.remove("./data/moduleDatabase/" + uid + ".json")
                    continue
                with open("./data/moduleDatabase/" + uid + ".json",
                          "w+") as file:
                    file.seek(0)
                    file.write(
                        json.dumps(module, default=lambda o: o.__dict__))
                    file.truncate()
        except Exception as e:
            logging.error(e)
            return False
        # Safe module_entrys
        try:
            logging.debug("Saving module entrys to database.")

            delete_able_files = [f for f in os.listdir(
                "./data/jobDatabase/") if f.endswith(".json")
                and (f.split(".")[0] not in
                     self.module_entrys.keys())]
            for delete_able_file in delete_able_files:
                os.remove("./data/jobDatabase/" + delete_able_file)

            for uid, module in self.module_entrys.items():
                with open("./data/jobDatabase/" + uid + ".json",
                          "w+") as file:
                    file.seek(0)
                    file.write(
                        json.dumps(module, default=safe_serialize))
                    file.truncate()
        except Exception as e:
            logging.error(e)
            return False
        # Safe queue
        try:
            logging.debug("Saving queue to database.")
            with open("./data/queue.json", "w+") as file:
                file.seek(0)
                file.write(json.dumps(
                    self.queue.queue, default=lambda o: o.__dict__))
                file.truncate()
        except Exception as e:
            logging.error(e)
            return False

    def add_module(self, module: Default) -> bool:
        """
        Adds a job to the Database
        :param module: The corresponding module
        :return: Nothing
        """
        try:
            logging.debug("Adding job with id " + module.module_uid
                          + " to database.")
            self.modules[module.module_uid] = module
            return True
        except Exception as e:
            logging.error(e)
            return False

    def add_job(self, module_entry: Default.Entry) -> bool:
        """
        Adds a job to the Database
        :param module_entry: The corresponding module entry
        :return: Nothing
        """
        try:
            logging.debug("Adding job with id " + module_entry.uid
                          + " to database.")
            self.module_entrys[module_entry.uid] = module_entry
            return True
        except Exception as e:
            logging.error(e)
            return False

    def load_job(self, uid: str) -> Default.Entry:
        """
        Loads a job for a given uid
        :param uid: The uid from the job to load
        :return: The job data as a json object
        """
        logging.debug("Loading job with id " + uid + " from database.")
        return self.module_entrys[uid]

    def delete_job(self, uid: str) -> bool:
        """
        Deletes a job for a given uid
        :param uid: The uid from the job to delete
        :return: Nothing
        """
        try:
            logging.debug("Deleting job with id " + uid + " from database.")
            self.module_entrys.pop(uid)
            return True
        except Exception as e:
            logging.error(e)
            return False

    def exists_job(self, uid: str) -> bool:
        """
        Checks if a job for a given uid exists
        :param uid: The uid from the job to check
        :return: True or False (Exists or not)
        """
        logging.debug("Checking existence of job with id " + uid + " in "
                                                                   "database.")
        return self.module_entrys.get(uid) is not None

    def change_job_entry(self, uid: str, entry: str, input) -> bool:
        """
        Changes the status of the corresponding job
        :param input: The input for the entry
        :param uid: The module_entry_id from the job
        :param entry: The entry to set it to
        :return: Nothing
        """
        try:
            logging.debug(f"Changing {entry} of job with id "
                          + uid + f" to {input}.")
            module_entry: Default.Entry = self.module_entrys.get(uid)
            setattr(module_entry, entry, input)
            return True
        except Exception as e:
            logging.error(e)
            return False
