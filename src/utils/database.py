import json
import logging
import os
from pydoc import locate

from queue import PriorityQueue
from typing import Dict

from packages.Default import Default
from utils import util


def add_job(module_entry: Default.Entry):
    """
    Adds a job to the Database
    :param module_entry: The corresponding module entry
    :param uid: The uid for the job
    :return: Nothing
    """
    logging.debug("Adding job with id " + module_entry.uid + " to database.")
    job_data: str = json.dumps(module_entry, default=lambda o: o.__dict__)
    with open("./data/jobDatabase/" + module_entry.uid + ".json", "x") as file:
        file.write(job_data)
        file.close()


def load_job(uid: str):
    """
    Loads a job for a given uid
    :param uid: The uid from the job to laod
    :return: The job data as a json object
    """
    logging.debug("Loading job with id " + uid + " from database.")
    with open("./data/jobDatabase/" + uid + ".json", "r") as file:
        job_data_raw = json.load(file)
        job_data_type: type = job_data_raw["module"]["module_type"] + ".Entry"
        job_data: job_data_type = job_data_raw
        return job_data


def delete_job(uid: str):
    """
    Deletes a job for a given uid
    :param uid: The uid from the job to delete
    :return: Nothing
    """
    logging.debug("Deleting job with id " + uid + " from database.")
    os.remove("./data/jobDatabase/" + uid + ".json")


def exists_job(uid: str):
    """
    Checks if a job for a given uid exists
    :param uid: The uid from the job to check
    :return: True or False (Exists or not)
    """
    logging.debug("Checking existence of job with id " + uid + " in database.")
    return os.path.exists("./data/jobDatabase/" + uid + ".json")


def change_job_status(module_entry: Default.Entry, status: int):
    """
    Changes the status of the corresponding job
    :param module_entry: The module_entry from the job
    :param status: The status id to set it to
    :return: Nothing
    """
    logging.debug("Changing status of job with id "
                  + module_entry.uid + " to " + util.get_status(status) + ".")
    with (open("./data/jobDatabase/" + module_entry.uid + ".json", "r+") as
          file):
        job_data = json.load(file)
        job_data["status"] = status
        file.seek(0)
        file.write(json.dumps(job_data))
        file.truncate()


def set_whisper_result(module_entry: Default.Entry, whisper_result: {}):
    """
    Sets the Whisper result of the corresponding job
    :param module_entry: The module_entry from the job
    :param whisper_result: The Whisper result to set
    :return: Nothing
    """
    logging.debug("Adding whisper result to job with id " + module_entry.uid
                  + ".")
    with (open("./data/jobDatabase/" + module_entry.uid + ".json", "r+") as
          file):
        job_data = json.load(file)
        job_data["whisper_result"] = whisper_result
        file.seek(0)
        file.write(json.dumps(job_data))
        file.truncate()


def set_whisper_language(module_entry: Default.Entry, whisper_language: str):
    """
    Sets the language of the corresponding job
    :param module_entry: The module_entry from the job
    :param whisper_language: The language to set
    :return: Nothing
    """
    logging.debug("Adding whisper language to job with id " +
                  module_entry.uid + ".")
    with (open("./data/jobDatabase/" + module_entry.uid + ".json", "r+") as
          file):
        job_data = json.load(file)
        job_data["whisper_language"] = whisper_language
        file.seek(0)
        file.write(json.dumps(job_data))
        file.truncate()


def set_whisper_model(module_entry: Default.Entry, whisper_model: str):
    """
    Sets the language of the corresponding job
    :param module_entry: The module_entry from the job
    :param whisper_model: The model to set
    :return: Nothing
    """
    logging.debug("Adding whisper model to job with id " + module_entry.uid
                  + ".")
    with (open("./data/jobDatabase/" + module_entry.uid + ".json", "r+") as
          file):
        job_data = json.load(file)
        job_data["whisper_model"] = whisper_model
        file.seek(0)
        file.write(json.dumps(job_data))
        file.truncate()


def save_queue(queue: PriorityQueue[(int, Default.Entry)]):
    """
    Saves the given queue to the database
    :param queue: The queue to save
    :return: Nothing
    """
    logging.debug("Saving queue to database.")
    with open("./data/queue.json", "w+") as file:
        file.seek(0)
        file.write(json.dumps(queue.queue, default=lambda o: o.__dict__))
        file.truncate()


def save_modules(modules: Dict[str, Default]):
     """
     Saves the given queue to the database
     :param modules: The queue to save
     :return: Nothing
     """
     logging.debug("Saving Modules to database.")
     for uid, module in modules.items():
        #if len(module.entrys) == 0:
        #    if os.path.exists("./data/moduleDatabase/" + uid + ".json"):
        #        os.remove("./data/moduleDatabase/" + uid + ".json")
        #    continue
        with open("./data/moduleDatabase/" + uid + ".json",
                  "w+") as file:
            file.seek(0)
            file.write(json.dumps(module, default=lambda o: o.__dict__))
            file.truncate()


def load_modules():
    """
    Saves the given queue to the database
    :return: All used Opencast Modules
    """
    logging.debug("Loading Modules from database.")
    modules: Dict[str, Default] = {}
    for file_name in os.listdir("./data/moduleDatabase"):
        if file_name.endswith(".json"):
            file_path = os.path.join("./data/moduleDatabase", file_name)
            with open(file_path, "r", encoding="utf-8") as file:
                module_data_raw = json.load(file)
                module_type: object = locate(module_data_raw["module_type"])
                module: module_type = module_type(**module_data_raw)
                modules[module.module_uid] = module
    return modules


def load_queue() -> PriorityQueue[(int, Default.Entry)]:
    """
    Loads the queue from the database
    :return: PriorityQueue
    """
    logging.debug("Loading queue to database.")
    queue: PriorityQueue[(int, Default.Entry)] = PriorityQueue()
    if os.path.exists("./data/queue.json"):
        with (open("./data/queue.json", "r") as file):
            queue_data = json.load(file)
            while len(queue_data) > 0:
                priority, job_data_raw = queue_data.pop()
                # Get module and module entry type
                module_type: object = locate(job_data_raw["module"][
                                       "module_type"])
                entry_type: object = locate(job_data_raw["module"][
                                       "module_type"] + ".Entry")

                # Dynamic rebuild module
                module: module_type = module_type(**job_data_raw["module"])
                job_data_raw["module"] = module

                # Dynamic rebuild module entry
                job_data: entry_type = entry_type(**job_data_raw)

                # Rebuild queue
                queue.put((priority, job_data))
    return queue
