import json
import logging
import os

from queue import PriorityQueue

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
    job_data = {"id": module_entry.uid,
                "module_id": module_entry.default.module_uid,
                "status": 0}
    with open("./data/jobDatabase/" + module_entry.uid + ".json", "x") as file:
        file.write(json.dumps(job_data))
        file.close()


def load_job(uid: str):
    """
    Loads a job for a given uid
    :param uid: The uid from the job to laod
    :return: The job data as a json object
    """
    logging.debug("Loading job with id " + uid + " from database.")
    with open("./data/jobDatabase/" + uid + ".json", "r") as file:
        job_data = json.load(file)
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
        file.write(json.dumps(queue.queue))
        file.truncate()


# def save_module(modules: Dict[str, Default]):
#     """
#     Saves the given queue to the database
#     :param modules: The queue to save
#     :return: Nothing
#     """
#     logging.debug("Saving Modules to database.")
#     for uid, module in modules.items():
#         if len(module.entrys) == 0:
#             if os.path.exists("./data/moduleDatabase/" + uid + ".json"):
#                 os.remove("./data/moduleDatabase/" + uid + ".json")
#             continue
#         with open("./data/moduleDatabase/" + uid + ".json",
#                   "w+") as file:
#             file.seek(0)
#             file.write(json.dumps(module))
#             file.truncate()
#
#
# def load_modules():
#     """
#     Saves the given queue to the database
#     :return: All used Opencast Modules
#     """
#     logging.debug("Loading Opencast Module from database.")
#     modules: Dict[str, Default] = {}
#     for file_name in os.listdir("./data/moduleDatabase"):
#         if file_name.endswith(".json"):
#             file_path = os.path.join("./data/moduleDatabase", file_name)
#             with open(file_path, "r", encoding="utf-8") as file:
#                 data = json.load(file)
#             modules[data.get("uid")] = Opencast(
#                 data.get("max_queue_entry"),
#                 data.get("uid"), data.get(
#                     "queue_entry"), data.get("link_list"))
#    return modules


def load_queue() -> PriorityQueue[(int, Default.Entry)]:
    """
    Loads the queue from the database
    :return: PriorityQueue
    """
    logging.debug("Loading queue to database.")
    queue: PriorityQueue[(int, Default.Entry)] = PriorityQueue()
    #if os.path.exists("./data/queue.json"):
    #    with open("./data/queue.json", "r") as file:
    #        queue_data = json.load(file)
    #        while len(queue_data) > 0:
    #            data = queue_data.pop()
    #            queue.put((data[0], data[1]))
    return queue
