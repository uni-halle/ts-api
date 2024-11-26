import logging
import os
import signal
import threading
import time
from queue import PriorityQueue
from typing import List, Dict

import whisper

from core.Transcriber import Transcriber
from packages.Opencast import Opencast
from utils import database


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
        self.opencastModules: Dict[str, Opencast] = (
            database.load_opencast_modules())
        model_size = os.environ.get("whisper_model")
        if not os.path.exists("./data/models/" + model_size + ".pt"):
            logging.info("Downloading Whisper model...")
            whisper.load_model(model_size, download_root="./data/models")
        logging.info("Whisper model \"" + model_size + "\" loaded!")
        logging.info("TsAPI started!")
        self.running: bool = True

    def exit(self, sig, frame):
        """
        Managing saving of queue and stopping api
        """
        logging.info("Stopping TsAPI...")
        self.running = False
        database.save_opencast_module(self.opencastModules)
        for uid in self.runningJobs:
            logging.info("Requeue job with id " + uid + " because of "
                                                        "shutdown.")
            database.change_job_status(uid, 1)  # Prepared
            self.queue.put((0, (uid, None)))
        database.save_queue(self.queue)
        logging.info("TsAPI stopped!")
        os.kill(os.getpid(), signal.SIGKILL)

    def add_to_queue(self, uid: str, module_id, priority: int):
        """
        Adds job to queue
        :param module_id: The corresponding module id (if available)
        :param uid: The uid of the job
        :param priority: The priority of the job itself
        :return: The uid the job got assigned
        """
        logging.info("Adding job with id " + uid + " to queue.")
        # Add job to queue
        self.queue.put((priority, (uid, module_id)))

    # Track running jobs
    def register_job(self, uid: str):
        """
        Register a running job
        :param uid: The uid of the job
        :return: The transcriber model the registered job prepared
        """
        logging.info("Starting job with id " + uid + ".")
        # Create transcriber
        trans = Transcriber(self, uid)
        # Return prepared transcriber
        return trans

    def unregister_job(self, uid: str):
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
                    # Peek Job from Queue
                    uid: str
                    module_id: str
                    with self.queue.mutex:
                        uid, module_id = self.queue.queue[0][1]
                    self.runningJobs.append(uid)
                    # Checking module
                    if module_id:
                        # Opencast Module
                        if module_id in self.opencastModules:
                            logging.info("Preprocessing job with id " + uid
                                         + ".")
                            # ModuleID found
                            opencast_module: Opencast = self.opencastModules[
                                module_id]
                            opencast_module.download_file(uid)
                            opencast_module.queue_entry = (
                                opencast_module.queue_entry - 1)
                    # Change Status to prepared
                    database.change_job_status(uid, 1)  # Prepared
                    # Remove Job From Queue
                    self.queue.get()
                    # Register job
                    trans: Transcriber = self.register_job(uid)
                    # Start job
                    trans.start_thread()
            time.sleep(5)
