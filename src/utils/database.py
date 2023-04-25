import json
import logging
import os

from queue import PriorityQueue

from utils import util


def add_job(filename: str, uid: str):
    """
    Adds a job to the Database
    :param filename: The name of the jobs file
    :param uid: The uid for the job
    :return: Nothing
    """
    logging.debug("Adding job with id " + uid + " to database.")
    job_data = {"id": uid,
                "filename": uid + os.path.splitext(filename)[1],
                "status": 0}
    with open("./data/jobDatabase/" + uid + ".json", "x") as file:
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
    job_data = load_job(uid)
    os.remove("./data/jobDatabase/" + uid + ".json")


def exists_job(uid: str):
    """
    Checks if a job for a given uid exists
    :param uid: The uid from the job to check
    :return: True or False (Exists or not)
    """
    logging.debug("Checking existence of job with id " + uid + " in database.")
    return os.path.exists("./data/jobDatabase/" + uid + ".json")


def change_job_status(uid: str, status: int):
    """
    Changes the status of the corresponding job
    :param uid: The uid from the job
    :param status: The status id to set it to
    :return: Nothing
    """
    logging.debug("Changing status of job with id " + uid + " to " + util.get_status(status) + ".")
    with open("./data/jobDatabase/" + uid + ".json", "r+") as file:
        job_data = json.load(file)
        job_data["status"] = status
        file.seek(0)
        file.write(json.dumps(job_data))
        file.truncate()


def set_whisper_result(uid: str, whisper_result: {}):
    """
    Sets the Whisper result of the corresponding job
    :param uid: The uid from the job
    :param whisper_result: The Whisper result to set
    :return: Nothing
    """
    logging.debug("Adding whisper result to job with id " + uid + ".")
    with open("./data/jobDatabase/" + uid + ".json", "r+") as file:
        job_data = json.load(file)
        job_data["whisper_result"] = whisper_result
        file.seek(0)
        file.write(json.dumps(job_data))
        file.truncate()


def set_whisper_language(uid: str, whisper_language: str):
    """
    Sets the language of the corresponding job
    :param uid: The uid from the job
    :param whisper_language: The language to set
    :return: Nothing
    """
    logging.debug("Adding whisper language to job with id " + uid + ".")
    with open("./data/jobDatabase/" + uid + ".json", "r+") as file:
        job_data = json.load(file)
        job_data["whisper_language"] = whisper_language
        file.seek(0)
        file.write(json.dumps(job_data))
        file.truncate()


def save_queue(queue: PriorityQueue):
    """
    Saves the given queue to the database
    :param queue: The queue to save
    :return: Nothing
    """
    logging.debug("Saving queue to database.")
    with open("./data/jobDatabase/queue.json", "w+") as file:
        file.seek(0)
        file.write(json.dumps(queue.queue))
        file.truncate()


def load_queue():
    """
    Loads the queue from the database
    :return: PriorityQueue
    """
    logging.debug("Loading queue to database.")
    queue = PriorityQueue()
    if os.path.exists("./data/jobDatabase/queue.json"):
        with open("./data/jobDatabase/queue.json", "r") as file:
            queue_data = json.load(file)
            while len(queue_data) > 0:
                data = queue_data.pop()
                queue.put((data[0], data[1]))
    return queue
