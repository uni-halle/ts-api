import logging
import threading
import os
import time
from multiprocessing import Process, Queue

from core import whisper_worker
from packages.Default import Default
from utils.database import JobStatus


class Transcriber:
    """Transcriber with true cancellation support via multiprocessing"""

    def __init__(self, ts_api, module_entry: Default.Entry,
                 cancel_event: threading.Event):
        """
        Creates a Transcriber object to work on subtitles

        Args:
            ts_api: The main ts_api object to call back
            module_entry: The module_entry of the job to transcribe
            cancel_event: Threading event for cancellation support
        """
        self.whisper_result = None
        self.whisper_language = None
        self.file_path: str = "./data/audioInput/" + module_entry.uid
        self.ts_api = ts_api
        self.module_entry: Default.Entry = module_entry
        self.cancel_event = cancel_event
        self.transcription_process = None

    def transcribe(self):
        """
        Transcribe audio with true cancellation support
        Uses multiprocessing to allow killing the transcription process
        """
        try:
            logging.info(f"Starting transcription for job "
                         f"{self.module_entry.uid}")

            if self.cancel_event.is_set():
                self._handle_cancellation()
                return

            self.ts_api.database.update_job_status(
                self.module_entry.uid,
                JobStatus.PROCESSING,
                started_at=time.time()
            )

            initial_prompt = None
            if (hasattr(self.module_entry, "initial_prompt")
                    and self.module_entry.initial_prompt):
                initial_prompt = self.module_entry.initial_prompt

            result_queue = Queue()
            self.transcription_process = Process(
                target=whisper_worker.run,
                args=(self.file_path, initial_prompt, result_queue)
            )
            self.transcription_process.start()

            # Poll for completion or cancellation
            while self.transcription_process.is_alive():
                if self.cancel_event.is_set():
                    logging.info(f"Cancellation requested for job "
                                 f"{self.module_entry.uid} - terminating "
                                 f"process")
                    self._stop_process()
                    self._handle_cancellation()
                    return
                time.sleep(0.5)

            self.transcription_process.join()

            result_data = None
            while not result_queue.empty():
                message = result_queue.get()
                if message["type"] == "language":
                    self.whisper_language = message["language"]
                    self.ts_api.database.change_job_entry(
                        self.module_entry.uid, "whisper_model",
                        message["model"])
                    self.ts_api.database.change_job_entry(
                        self.module_entry.uid, "whisper_language",
                        self.whisper_language)
                else:
                    result_data = message

            if result_data is None:
                raise Exception("Transcription process exited without result")
            if result_data["type"] == "error":
                raise Exception(result_data["error"])

            self.whisper_result = result_data["segments"]
            if result_data["vad_segments"]:
                self.ts_api.database.change_job_entry(
                    self.module_entry.uid, "vad_segments",
                    result_data["vad_segments"])
            self.ts_api.database.update_job_status(
                self.module_entry.uid,
                JobStatus.COMPLETED,
                whisper_result=self.whisper_result,
                completed_at=time.time()
            )

            if os.path.exists(self.file_path):
                os.remove(self.file_path)
            logging.info(f"Successfully completed job "
                         f"{self.module_entry.uid}")

        except Exception as e:
            logging.error(f"Error transcribing job "
                          f"{self.module_entry.uid}: {e}")
            self.ts_api.database.update_job_status(
                self.module_entry.uid,
                JobStatus.FAILED,
                error_message=str(e),
                completed_at=time.time()
            )
            if os.path.exists(self.file_path):
                try:
                    os.remove(self.file_path)
                except OSError:
                    pass
            self._stop_process()

    def _stop_process(self):
        """Terminate the transcription process, kill it if necessary"""
        process = self.transcription_process
        if process and process.is_alive():
            process.terminate()
            process.join(timeout=5)
            if process.is_alive():
                logging.warning("Process didn't terminate gracefully, "
                                "killing it")
                process.kill()
                process.join()

    def _handle_cancellation(self):
        """Handle job cancellation cleanly"""
        logging.info(f"Handling cancellation for job "
                     f"{self.module_entry.uid}")
        self.ts_api.database.update_job_status(
            self.module_entry.uid,
            JobStatus.CANCELED,
            completed_at=time.time()
        )
        if os.path.exists(self.file_path):
            try:
                os.remove(self.file_path)
            except Exception as e:
                logging.error(f"Failed to remove audio file for canceled "
                              f"job {self.module_entry.uid}: {e}")
