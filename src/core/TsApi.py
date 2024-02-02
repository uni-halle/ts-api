import io
import logging
import os
import signal
import sys
import threading
import time
from queue import PriorityQueue
from typing import List

import requests
from requests import request
from werkzeug.datastructures import FileStorage

from core.Transcriber import Transcriber
from utils import util, database


class TsApi:

    def __init__(self):
        """
        The Core of the program, manages the queue and running jobs.
        """
        logging.info("Starting TsAPI...")
        signal.signal(signal.SIGINT, self.exit)
        signal.signal(signal.SIGTERM, self.exit)
        self.queue: PriorityQueue = database.load_queue()
        self.runningJobs: List[str] = []
        self.runningDownloads: List[str] = []
        self.running: bool = True
        logging.info("TsAPI started!")

    def exit(self, sig, frame):
        """
        Managing saving of queue and stopping api
        """
        logging.info("Stopping TsAPI...")
        self.running = False
        database.save_queue(self.queue)
        while len(self.runningJobs) > 0:
            logging.info("Waiting for job to finish...")
            time.sleep(10)
        logging.info("TsAPI stopped!")
        sys.exit(1)

    def add_file_to_queue(self, uid: str, file: FileStorage, priority: int):
        """
        Adds job to queue
        :param uid: The uid of the job
        :param file: The file the job should process
        :param priority: The priority of the job itself
        :return: The uid the job got assigned
        """
        logging.info("Adding job with id " + uid + " to queue.")
        # Safe file to input folder
        util.save_file(file, uid)
        # Add job to database
        database.add_job(file.filename, uid)
        # Add job to queue
        self.queue.put((priority, uid))

    def add_link_to_queue(self, uid: str, link: str, priority: int,
                          username: str = None, password: str = None):
        """
        Adds job to queue
        :param uid: The uid of the job
        :param link: The link the job should process
        :param username: The username to log in to the website
        :param password: The password to log in to the website<
        :param priority: The priority of the job itself
        :return: The uid the job got assigned
        """
        try:
            logging.info("Downloading file for job id " + uid + "...")
            self.runningDownloads.append(uid)
            session: request = requests.Session()
            # Add job to database
            database.add_job(uid, uid)
            # Check if username and password is present
            if username and password:
                session.auth = (username, password)
            # Get Response
            response = session.get(link, allow_redirects=False)
            # Check Response
            if response.status_code != 200:
                raise Exception
            file = FileStorage(
                stream=io.BytesIO(response.content),
                filename=uid,
                content_length=response.headers.get("Content-Length"),
                content_type=response.headers.get("Content-Type")
            )
            logging.info("Downloaded file for job id " + uid + ".")
            # Safe file to input folder
            util.save_file(file, uid)
            self.runningDownloads.remove(uid)
            logging.info("Adding job with id " + uid + " to queue.")
            # Add job to queue
            self.queue.put((priority, uid))
        except:
            database.change_job_status(uid, 3)  # Failed
            logging.error("Error downloading or adding job "
                          + uid + " to queue.")

    # Track running jobs
    def register_job(self, uid):
        """
        Register a running job
        :param uid: The uid of the job
        :return: The transcriber model the registered job prepared
        """
        logging.info("Starting job with id " + uid + ".")
        # Create transcriber
        trans = Transcriber(self, uid)
        # Add running job
        self.runningJobs.append(uid)
        # Return prepared transcriber
        return trans

    def unregister_job(self, uid):
        """
        Unregister a finished job
        :param uid: The uid of the job
        :return: Nothing
        """
        # Remove finished Job
        logging.info("Finished job with id " + uid + ".")
        self.runningJobs.remove(uid)

    # Thread to manage queue
    def start_thread(self):
        """
        Start the thread for managing queue and running jobs
        :return: Nothing
        """
        ts_api_thread = threading.Thread(target=self.ts_api_thread)
        ts_api_thread.start()

    def ts_api_thread(self):
        """
        Manages queue and starts a new job if resources are available
        :return: Nothing
        """
        while self.running:
            parallel_worker = int(os.environ.get("parallel_workers"))
            if len(self.runningJobs) < parallel_worker:
                if not self.queue.empty():
                    uid = self.queue.get()[1]
                    # Register running job
                    trans: Transcriber = self.register_job(uid)
                    # Start running job
                    trans.start_thread()
            time.sleep(5)
