import logging
import os
import signal
import threading
import time
from queue import PriorityQueue
from typing import List, Dict

import whisper

from packages.File import File
from core.Transcriber import Transcriber
from packages.Default import Default
from utils import database


class TsApi:

    def __init__(self):
        """
        Initialisiert die TsAPI-Klasse und startet den Dienst.

        Initialisiert die Warteschlange und laufende Jobs, lädt das
        Whisper-Modell und richtet Signalhandler für das Herunterfahren ein.
        """
        logging.info("Starting TsAPI...")
        # Shutdown Handling
        signal.signal(signal.SIGINT, self.exit)
        signal.signal(signal.SIGTERM, self.exit)
        # Queue and Running Jobs
        self.queue: PriorityQueue[(int, Default.Entry)] = database.load_queue()
        self.running_jobs: List[Default.Entry] = []
        # Load & Create Module
        self.modules: Dict[str, Default] = database.load_modules()
        if len(self.modules) == 0:
            self.file_module = File(module_uid="DefaultFileModule")
            self.modules["DefaultFileModule"] = self.file_module
        else:
            self.file_module = self.modules["DefaultFileModule"]
        # Load Whisper Model
        model_size = os.environ.get("whisper_model")
        if not os.path.exists("./data/models/" + model_size + ".pt"):
            logging.info("Downloading Whisper model...")
            whisper.load_model(model_size, download_root="./data/models")
        logging.info(f"Whisper model \"{model_size}\" loaded!")
        logging.info("TsAPI started!")
        self.running: bool = True

    def exit(self, sig, frame):
        """
        Beendet TsAPI und speichert die aktuelle Warteschlange.

        Läuft bei einem Beenden-Signal und sichert laufende Jobs erneut in
        die Warteschlange.
        """
        logging.info("Stopping TsAPI...")
        self.running = False
        database.save_modules(self.modules)
        for module_entry in self.running_jobs:
            logging.info(f"Requeue job with id {module_entry.uid}"
                         + " because of shutdown.")
            database.change_job_status(module_entry, 1)  # Prepared
            self.add_to_queue(0, module_entry)
        database.save_queue(self.queue)
        logging.info("TsAPI stopped!")
        os.kill(os.getpid(), signal.SIGKILL)

    def add_to_queue(self, priority: int, module_entry: Default.Entry) -> None:
        """
        Fügt einen Job zur Warteschlange hinzu.

        :param priority: Die Priorität des Jobs.
        :param module_entry: Der Eintrag, der zur Warteschlange hinzugefügt
        werden soll.
        """
        logging.info(f"Adding job with id {module_entry.uid} to queue.")
        try:
            database.add_job(module_entry)
            self.queue.put((priority, module_entry))
        except Exception as e:
            logging.error(f"Error adding job {module_entry.uid} to queue: {e}")

    # Track running jobs
    def register_job(self, entry: Default.Entry) -> Transcriber:
        """
        Registriert einen laufenden Job und erstellt einen Transcriber.

        :param entry: Der Eintrag des Jobs.
        :return: Der vorbereitete Transcriber.
        """
        logging.info(f"Starting job with id {entry.uid}.")
        trans = Transcriber(self, entry)
        return trans

    def unregister_job(self, entry: Default.Entry) -> None:
        """
        Entfernt einen abgeschlossenen Job aus der laufenden Job-Liste.

        :param entry: Der Eintrag des abgeschlossenen Jobs.
        """
        logging.info(f"Finished job with id {entry.uid}.")
        self.running_jobs.remove(entry)
        del entry.module.entrys[entry.uid]

    # Thread to manage queue
    def start_thread(self) -> None:
        """
        Startet den Thread zur Verwaltung der Warteschlange und laufenden Jobs.
        """
        ts_api_thread = threading.Thread(target=self.ts_api_thread)
        ts_api_thread.start()

    def ts_api_thread(self) -> None:
        """
        Verarbeitet die Warteschlange und startet neue Jobs, wenn Ressourcen
        verfügbar sind.

        Läuft in einem separaten Thread und verarbeitet die Warteschlange,
        indem es Jobs je nach Verfügbarkeit ausführt.
        """
        while self.running:
            parallel_worker = int(os.environ.get("parallel_workers"))
            if len(self.running_jobs) < parallel_worker:
                if not self.queue.empty():
                    try:
                        module_entry: Default.Entry = self.queue.get(
                            timeout=1)[1]
                        self.running_jobs.append(module_entry)
                        # Preparing
                        logging.info(f"Started preparing job with id"
                                     f" {module_entry.uid}.")
                        module_entry.preprocessing()
                        logging.info(f"Finished preparing job with id"
                                     f" {module_entry.uid}.")
                        database.change_job_status(module_entry, 1)  # Prepared
                        # Whispering
                        trans: Transcriber = self.register_job(module_entry)
                        trans.start_thread()
                    except Exception as e:
                        logging.error(f"Error processing job: {e}")
                        database.change_job_status(module_entry, 5)  # Canceled
            time.sleep(5)
