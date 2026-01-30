import logging
import os
import signal
import sys
import threading
import time
from typing import List

from faster_whisper import WhisperModel

from packages.File import File
from core.Transcriber import Transcriber
from packages.Default import Default
from utils.database import Database


class TsApi:

    def __init__(self):
        """
        Initialisiert die TsAPI-Klasse und startet den Dienst.

        Initialisiert die Warteschlange und laufende Jobs, lädt das
        Whisper-Modell und richtet Signalhandler für das Herunterfahren ein.
        """
        logging.info("Starting TsAPI...")
        # Shutdown Handling
        signal.signal(signal.SIGTERM, self.exit)
        signal.signal(signal.SIGINT, self.exit)
        # Creating/Loading Database
        self.database = Database()
        # Queue and Running Jobs
        self.running_jobs: List[Default.Entry] = []
        # Load & Create Module
        if "DefaultFileModule" not in self.database.modules:
            self.file_module = File(module_uid="DefaultFileModule")
            self.database.modules["DefaultFileModule"] = self.file_module
        else:
            self.file_module = self.database.modules["DefaultFileModule"]
        # Load Whisper Model (faster-whisper downloads automatically if needed)
        model_size = os.environ.get("whisper_model")
        device = os.environ.get("whisper_device", "cuda")
        compute_type = os.environ.get("whisper_compute_type", "float16")
        cpu_threads = int(os.environ.get("whisper_cpu_threads", "4"))
        
        try:
            logging.info(f"Initializing Whisper model '{model_size}' on {device}...")
            # This will download the model if it doesn't exist
            model_kwargs = {
                "device": device,
                "compute_type": compute_type,
                "download_root": "./data/models"
            }
            if device == "cpu":
                model_kwargs["cpu_threads"] = cpu_threads
            
            test_model = WhisperModel(model_size, **model_kwargs)
            logging.info(f"Whisper model \"{model_size}\" loaded successfully!")
            del test_model  # Free memory
        except Exception as e:
            logging.error(f"Failed to load Whisper model: {e}")
            raise
        
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
        for module_entry in self.running_jobs:
            logging.info(f"Requeue job with id {module_entry.uid}"
                         + " because of shutdown.")
            self.database.change_job_entry(module_entry.uid, "status",
                                           0)  # Queued
            module_entry.priority = 0
            self.database.queue.put((module_entry.priority, module_entry))
        self.database.save_database()
        logging.info("TsAPI stopped!")
        sys.exit(0)

    def add_to_queue(self, priority: int, module_entry: Default.Entry) -> None:
        """
        Fügt einen Job zur Warteschlange hinzu.

        :param priority: Die Priorität des Jobs.
        :param module_entry: Der Eintrag, der zur Warteschlange hinzugefügt
        werden soll.
        """
        logging.info(f"Adding job with id {module_entry.uid} to queue.")
        try:
            self.database.add_job(module_entry)
            self.database.change_job_entry(module_entry.uid, "status", 0)
            self.database.queue.put((priority, module_entry))
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
        entry.module.queued_or_active = entry.module.queued_or_active - 1
        # ERROR!?
        self.running_jobs.remove(entry)

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
                if not self.database.queue.empty():
                    try:
                        module_entry: Default.Entry = self.database.queue.get(
                            timeout=1)[1]
                        self.running_jobs.append(module_entry)
                        # Preparing
                        logging.info(f"Started preparing job with id"
                                     f" {module_entry.uid}.")
                        module_entry.preprocessing()
                        logging.info(f"Finished preparing job with id"
                                     f" {module_entry.uid}.")
                        self.database.change_job_entry(module_entry.uid,
                                                       "status", 1)  # Prepared
                        # Whispering
                        trans: Transcriber = self.register_job(module_entry)
                        trans.start_thread()
                    except Exception as e:
                        logging.error(f"Error processing job: {e}")
                        self.database.change_job_entry(module_entry.uid,
                                                       "status", 5)  # Canceled
            time.sleep(5)
