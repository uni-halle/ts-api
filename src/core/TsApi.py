import logging
import os
import signal
import threading
import time
from queue import PriorityQueue
from typing import List, Dict

import whisper

from core.Transcriber import Transcriber
from packages.Default import Default
from utils import database


class TsApi:

    def __init__(self):
        """
        The Core of the program, manages the queue and running jobs.
        """
        logging.info("Starting TsAPI...")
        signal.signal(signal.SIGINT, self.exit)
        signal.signal(signal.SIGTERM, self.exit)
        self.queue: PriorityQueue[(int, Default.Entry)] = database.load_queue()
        self.running_jobs: List[Default.Entry] = []
        self.default_module = Default()
        self.modules: Dict[str, Default] = {} #  database.load_modules()
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
        # database.save_modules(self.modules)
        for module_entry in self.running_jobs:
            logging.info("Requeue job with id " + module_entry.uid + " because of "
                                                        "shutdown.")
            database.change_job_status(module_entry, 1)  # Prepared
            self.add_to_queue(0, module_entry)
        database.save_queue(self.queue)
        logging.info("TsAPI stopped!")
        os.kill(os.getpid(), signal.SIGKILL)

    def add_to_queue(self, priority: int, module_entry: Default.Entry) -> None:
        """
        Adds job to queue
        :param module_entry: The corresponding module entry
        :param module_entry: The module_entry of the job
        :param priority: The priority of the job itself
        :return: The uid the job got assigned
        """
        logging.info("Adding job with id " + module_entry.uid + " to queue.")
        # Add job to queue
        self.queue.put((priority, module_entry))

    # Track running jobs
    def register_job(self, entry: Default.Entry):
        """
        Register a running job
        :param entry: The uid of the job
        :return: The transcriber model the registered job prepared
        """
        logging.info("Starting job with id " + entry.uid + ".")
        # Create transcriber
        trans = Transcriber(self, entry)
        # Return prepared transcriber
        return trans

    def unregister_job(self, entry: Default.Entry):
        """
        Unregister a finished job
        :param entry: The uid of the job
        :return: Nothing
        """
        # Remove finished Job
        logging.info("Finished job with id " + entry.uid + ".")
        self.running_jobs.remove(entry)

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
            if len(self.running_jobs) < parallel_worker:
                if not self.queue.empty():
                    module_entry: Default.Entry = self.queue.get(timeout=5)[1]
                    try:
                        self.running_jobs.append(module_entry)

                        logging.info("Started preparing job with id " +
                                     module_entry.uid
                                     + ".")
                        module_entry.preprocessing()
                        logging.info("Finished preparing job with id " +
                                     module_entry.uid
                                     + ".")

                        # Change Status to prepared
                        database.change_job_status(module_entry,
                                                   1)  # Prepared
                        # Register job
                        trans: Transcriber = self.register_job(module_entry)
                        # Start job
                        trans.start_thread()
                    except Exception:
                        # Change Status to prepared
                        database.change_job_status(module_entry,
                                                   5)  # Canceled
            time.sleep(5)
