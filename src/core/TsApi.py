import logging
import os
import signal
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future, CancelledError
from concurrent.futures import wait as wait_futures
from queue import PriorityQueue, Empty
from typing import Dict, List

from faster_whisper import download_model

from packages.File import File
from core.Transcriber import Transcriber
from packages.Default import Default, JobCanceled
from utils.database import Database, JobStatus


class TsApi:
    """
    Main API class.

    Jobs go through two stages that run independently of each other:
    preparation (e.g. downloading the file, up to "parallel_downloads" at
    the same time) and transcription (up to "parallel_workers" at the same
    time). A failing or hanging download only affects its own job.
    """

    def __init__(self):
        logging.info("Starting TsAPI...")

        # Shutdown handling
        signal.signal(signal.SIGTERM, self.exit)
        signal.signal(signal.SIGINT, self.exit)

        self.database = Database()

        self.parallel_workers = max(
            1, int(os.environ.get("parallel_workers", 1)))
        self.parallel_downloads = max(
            1, int(os.environ.get("parallel_downloads", 3)))
        # Limits how many files are downloaded in advance
        self.max_prepared_jobs = max(1, int(os.environ.get(
            "max_prepared_jobs",
            self.parallel_downloads + self.parallel_workers)))

        self.download_executor = ThreadPoolExecutor(
            max_workers=self.parallel_downloads,
            thread_name_prefix="download")
        self.transcribe_executor = ThreadPoolExecutor(
            max_workers=self.parallel_workers,
            thread_name_prefix="transcriber")

        # All of the following is guarded by job_lock
        self.job_lock = threading.RLock()
        self.wakeup = threading.Condition(self.job_lock)
        # Jobs waiting for preparation
        self.job_queue: PriorityQueue = PriorityQueue()
        # Prepared jobs waiting for transcription
        self.ready_queue: PriorityQueue = PriorityQueue()
        self.preparing: Dict[str, Future] = {}
        self.transcribing: Dict[str, Future] = {}
        self.cancel_events: Dict[str, threading.Event] = {}
        # Jobs that are counted in module.queued_or_active
        self.pending: Dict[str, Default.Entry] = {}

        self.running = False
        self.shutting_down = False

        # Load & create default file module
        if "DefaultFileModule" not in self.database.modules:
            self.file_module = File(module_uid="DefaultFileModule")
            self.database.add_module(self.file_module)
        else:
            self.file_module = self.database.modules["DefaultFileModule"]

        self._restore_queue()
        self.model_path = self._prepare_model()

        self.running = True
        logging.info("TsAPI started!")

    @staticmethod
    def _prepare_model() -> str:
        """
        Downloads the Whisper model if needed (without loading it)
        :return: The model path or name to pass to faster-whisper
        """
        model = os.environ.get("whisper_model", "large-v3-turbo")
        if os.environ.get("whisper_preload_model",
                          "true").lower() != "true" or os.path.isdir(model):
            return model
        logging.info(f"Checking/downloading Whisper model \"{model}\"...")
        try:
            path = download_model(model, cache_dir="./data/models")
        except Exception as e:
            logging.error(f"Failed to download Whisper model: {e}")
            raise
        logging.info(f"Whisper model \"{model}\" available!")
        return path

    def _restore_queue(self):
        """Requeue the jobs that were queued or running on shutdown"""
        restored = 0
        for priority, job_entry in self.database.load_queue():
            if job_entry.status in (JobStatus.COMPLETED, JobStatus.FAILED,
                                    JobStatus.CANCELED):
                self.database.remove_from_queue(job_entry.uid)
                continue
            if job_entry.uid in self.pending:
                continue
            self.database.update_job_status(job_entry.uid, JobStatus.QUEUED)
            self.pending[job_entry.uid] = job_entry
            self.job_queue.put((priority, job_entry))
            restored += 1

        # The counters are derived from the queue, so they cannot drift
        for module in self.database.modules.values():
            count = sum(1 for entry in self.pending.values()
                        if entry.module is module)
            if module.queued_or_active != count:
                self.database.update_module(module.module_uid,
                                            queued_or_active=count)
        logging.info(f"Loaded {restored} jobs from queue")

    def exit(self, sig, frame):
        """Graceful shutdown, unfinished jobs are requeued on next start"""
        if self.shutting_down:
            # A second signal must not interrupt the running shutdown
            return
        logging.info("Stopping TsAPI...")
        with self.wakeup:
            self.running = False
            self.shutting_down = True
            for event in self.cancel_events.values():
                event.set()
            futures = (list(self.preparing.values())
                       + list(self.transcribing.values()))
            self.wakeup.notify_all()

        self.download_executor.shutdown(wait=False, cancel_futures=True)
        self.transcribe_executor.shutdown(wait=False, cancel_futures=True)
        logging.info("Waiting for jobs to stop...")
        wait_futures(futures, timeout=20)

        self.database.sync()
        logging.info("TsAPI stopped!")
        sys.exit(0)

    def add_to_queue(self, priority: int, module_entry: Default.Entry) -> None:
        """Add a job to the queue"""
        logging.info(f"Adding job {module_entry.uid} to queue with priority "
                     f"{priority}")
        try:
            with self.wakeup:
                self.database.add_job(module_entry)
                self.database.update_job_status(module_entry.uid,
                                                JobStatus.QUEUED)
                self.database.add_to_queue(module_entry.uid, priority)
                self.database.update_module(
                    module_entry.module.module_uid,
                    queued_or_active=module_entry.module.queued_or_active)
                self.pending[module_entry.uid] = module_entry
                self.job_queue.put((priority, module_entry))
                self.wakeup.notify_all()
        except Exception as e:
            logging.error(f"Error adding job {module_entry.uid} to queue: "
                          f"{e}")

    def delete_job(self, job_id: str) -> bool:
        """
        Deletes a job. A job that is downloaded or transcribed right now is
        canceled first.
        :return: False if the job does not exist
        """
        with self.wakeup:
            if not self.database.exists_job(job_id):
                return False
            event = self.cancel_events.get(job_id)
            if event:
                logging.info(f"Canceling job {job_id}")
                event.set()
            in_progress = (job_id in self.preparing
                           or job_id in self.transcribing)
            self._release(job_id)
            self.database.delete_job(job_id)
            self.wakeup.notify_all()
        if not in_progress:
            self._remove_audio_file(job_id)
        return True

    def _release(self, job_id: str) -> None:
        """Removes a job from the queue and decrements the module counter"""
        with self.job_lock:
            self.cancel_events.pop(job_id, None)
            entry = self.pending.pop(job_id, None)
            if entry is None:
                return
            module = entry.module
            module.queued_or_active = max(0, module.queued_or_active - 1)
            self.database.update_module(
                module.module_uid, queued_or_active=module.queued_or_active)
            self.database.remove_from_queue(job_id)

    @staticmethod
    def _remove_audio_file(job_id: str) -> None:
        path = os.path.join("./data/audioInput", job_id)
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError as e:
            logging.error(f"Failed to remove audio file of job {job_id}: "
                          f"{e}")

    # Thread to manage queue
    def start_thread(self) -> None:
        """Start background worker threads"""
        self.queue_thread = threading.Thread(
            target=self._queue_worker,
            name="queue_worker",
            daemon=True
        )
        self.queue_thread.start()

        self.persistence_thread = threading.Thread(
            target=self._persistence_worker,
            name="persistence_worker",
            daemon=True
        )
        self.persistence_thread.start()

    def _queue_worker(self):
        """Starts downloads and transcriptions whenever a slot is free"""
        logging.info("Queue worker started")
        with self.wakeup:
            while self.running:
                try:
                    self._start_transcriptions()
                    self._start_preparations()
                except Exception as e:
                    logging.error(f"Error in queue worker: {e}")
                self.wakeup.wait(timeout=1)
        logging.info("Queue worker stopped")

    def _next_pending(self, queue: PriorityQueue):
        """Next job of the queue that has not been deleted in the meantime"""
        while True:
            try:
                _, job_entry = queue.get_nowait()
            except Empty:
                return None
            if job_entry.uid in self.pending:
                return job_entry

    def _start_preparations(self):
        while (len(self.preparing) < self.parallel_downloads
               and (len(self.preparing) + self.ready_queue.qsize()
                    < self.max_prepared_jobs)):
            job_entry = self._next_pending(self.job_queue)
            if job_entry is None:
                return
            logging.info(f"Preparing job {job_entry.uid}")
            event = self.cancel_events.setdefault(job_entry.uid,
                                                  threading.Event())
            future = self.download_executor.submit(job_entry.preprocessing,
                                                   event)
            self.preparing[job_entry.uid] = future
            future.add_done_callback(
                lambda f, entry=job_entry: self._on_prepared(entry, f))

    def _on_prepared(self, job_entry: Default.Entry, future: Future):
        with self.wakeup:
            self.preparing.pop(job_entry.uid, None)
            self.wakeup.notify_all()
            if self.shutting_down:
                # The job stays in the persisted queue
                return
            if job_entry.uid not in self.pending:
                # Deleted while it was prepared
                self._remove_audio_file(job_entry.uid)
                return
            try:
                error = future.exception()
            except CancelledError:
                error = JobCanceled()

            if error is None:
                logging.info(f"Prepared job {job_entry.uid}")
                self.database.update_job_status(job_entry.uid,
                                                JobStatus.PREPARED)
                self.ready_queue.put((job_entry.priority, job_entry))
                return

            if isinstance(error, JobCanceled):
                logging.info(f"Preparation of job {job_entry.uid} canceled")
                message = "Canceled"
            else:
                logging.error(f"Preparing job {job_entry.uid} failed: "
                              f"{error}")
                message = str(error)
            self.database.update_job_status(job_entry.uid,
                                            JobStatus.CANCELED,
                                            error_message=message,
                                            completed_at=time.time())
            self._release(job_entry.uid)
            self._remove_audio_file(job_entry.uid)

    def _start_transcriptions(self):
        while len(self.transcribing) < self.parallel_workers:
            job_entry = self._next_pending(self.ready_queue)
            if job_entry is None:
                return
            logging.info(f"Starting transcription of job {job_entry.uid}")
            event = self.cancel_events.setdefault(job_entry.uid,
                                                  threading.Event())
            transcriber = Transcriber(self, job_entry, event)
            future = self.transcribe_executor.submit(transcriber.transcribe)
            self.transcribing[job_entry.uid] = future
            future.add_done_callback(
                lambda f, entry=job_entry: self._on_transcribed(entry, f))

    def _on_transcribed(self, job_entry: Default.Entry, future: Future):
        with self.wakeup:
            self.transcribing.pop(job_entry.uid, None)
            self.wakeup.notify_all()
            if self.shutting_down:
                return
            if not future.cancelled() and future.exception():
                logging.error(f"Job {job_entry.uid} failed with exception: "
                              f"{future.exception()}")
                self.database.update_job_status(
                    job_entry.uid,
                    JobStatus.FAILED,
                    error_message=str(future.exception()),
                    completed_at=time.time()
                )
            self._release(job_entry.uid)

    def _persistence_worker(self):
        """Periodic database sync and health monitoring"""
        logging.info("Persistence worker started")

        while self.running:
            time.sleep(30)
            try:
                self.database.sync()
                stats = self.database.get_stats()
                with self.job_lock:
                    stats['downloading_jobs'] = len(self.preparing)
                    stats['running_jobs'] = len(self.transcribing)
                logging.debug(f"System health: {stats}")
            except Exception as e:
                logging.error(f"Error in persistence worker: {e}")

        logging.info("Persistence worker stopped")

    @property
    def queue_length(self) -> int:
        """Number of jobs that wait for (or are in) preparation"""
        with self.job_lock:
            return len(self.pending) - len(self.transcribing)

    @property
    def downloading_jobs(self) -> List[Default.Entry]:
        with self.job_lock:
            return [self.pending[uid] for uid in self.preparing
                    if uid in self.pending]

    @property
    def running_jobs(self) -> List[Default.Entry]:
        """Jobs that are transcribed right now"""
        with self.job_lock:
            return [self.pending[uid] for uid in self.transcribing
                    if uid in self.pending]
