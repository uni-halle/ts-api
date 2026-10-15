import logging
import multiprocessing
import os
import queue
import threading
import time

from core import whisper_worker
from packages.Default import Default
from utils.database import JobStatus

# "fork" is unsafe in a multi-threaded process (and with CUDA)
_mp = multiprocessing.get_context("spawn")


class Transcriber:
    """Transcribes one job in a separate process that can be terminated"""

    def __init__(self, ts_api, module_entry: Default.Entry,
                 cancel_event: threading.Event | None = None):
        """
        Creates a Transcriber object to work on subtitles
        :param ts_api: The main ts_api object to call back
        :param module_entry: The module_entry of the job to transcribe
        :param cancel_event: Is set to cancel the transcription
        """
        self.whisper_result = None
        self.whisper_language = None
        self.file_path: str = "./data/audioInput/" + module_entry.uid
        self.ts_api = ts_api
        self.module_entry: Default.Entry = module_entry
        self.cancel_event = cancel_event or threading.Event()
        self.transcription_process = None

    def transcribe(self) -> None:
        """
        Transcribes the audio file of the job and stores the result
        """
        uid = self.module_entry.uid
        try:
            logging.info(f"Starting transcription for job {uid}")
            if self.cancel_event.is_set():
                self._handle_cancellation()
                return

            self.ts_api.database.update_job_status(
                uid, JobStatus.PROCESSING, started_at=time.time())

            params = {
                "file_path": self.file_path,
                "model": getattr(self.ts_api, "model_path", None)
                or os.environ.get("whisper_model", "large-v3-turbo"),
                "initial_prompt": getattr(self.module_entry,
                                          "initial_prompt", None),
            }
            result_queue = _mp.Queue()
            self.transcription_process = _mp.Process(
                target=whisper_worker.run,
                args=(params, result_queue),
                name=f"whisper-{uid}",
                daemon=True
            )
            self.transcription_process.start()

            result = self._wait_for_result(result_queue)
            if result is None:
                self._handle_cancellation()
                return
            if result["type"] == "error":
                raise Exception(result["error"])

            self.whisper_result = result["segments"]
            if result.get("vad_segments"):
                self.ts_api.database.change_job_entry(
                    uid, "vad_segments", result["vad_segments"])
            self.ts_api.database.update_job_status(
                uid,
                JobStatus.COMPLETED,
                whisper_result=self.whisper_result,
                completed_at=time.time()
            )
            self._remove_audio_file()
            logging.info(f"Successfully completed job {uid}")

        except Exception as e:
            logging.error(f"Error transcribing job {uid}: {e}")
            self.ts_api.database.update_job_status(
                uid,
                JobStatus.FAILED,
                error_message=str(e),
                completed_at=time.time()
            )
            self._remove_audio_file()
        finally:
            self._stop_process()

    def _wait_for_result(self, result_queue):
        """
        Reads the messages of the transcription process until the result
        arrives. The queue has to be read while the process is running:
        a process does not exit before its queued data has been written
        to the pipe, which blocks for large results.
        :return: The result message, None if the job was canceled
        """
        timeout = float(os.environ.get("transcription_timeout", 0))
        deadline = time.monotonic() + timeout if timeout > 0 else None
        process = self.transcription_process
        while True:
            if self.cancel_event.is_set():
                return None
            if deadline and time.monotonic() > deadline:
                raise TimeoutError(f"Transcription not finished after "
                                   f"{timeout:g}s")
            try:
                message = result_queue.get(timeout=0.5)
            except queue.Empty:
                if process.is_alive():
                    continue
                try:
                    # The last message may still be on its way
                    message = result_queue.get(timeout=1)
                except queue.Empty:
                    raise Exception(f"Transcription process exited "
                                    f"unexpectedly (exit code "
                                    f"{process.exitcode})")

            if message["type"] == "language":
                self.whisper_language = message["language"]
                self.ts_api.database.change_job_entry(
                    self.module_entry.uid, "whisper_model",
                    message["model"])
                self.ts_api.database.change_job_entry(
                    self.module_entry.uid, "whisper_language",
                    self.whisper_language)
                continue
            return message

    def _stop_process(self):
        """Terminate the transcription process, kill it if necessary"""
        process = self.transcription_process
        if process is None:
            return
        if not self.cancel_event.is_set():
            # The process exits on its own after sending the result
            process.join(timeout=5)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
            if process.is_alive():
                logging.warning("Process didn't terminate gracefully, "
                                "killing it")
                process.kill()
                process.join()

    def _remove_audio_file(self):
        try:
            if os.path.exists(self.file_path):
                os.remove(self.file_path)
        except OSError as e:
            logging.error(f"Failed to remove audio file for job "
                          f"{self.module_entry.uid}: {e}")

    def _handle_cancellation(self):
        """Handle job cancellation cleanly"""
        uid = self.module_entry.uid
        self._stop_process()
        if getattr(self.ts_api, "shutting_down", False):
            # Keep the file, the job is requeued on the next start
            logging.info(f"Transcription of job {uid} interrupted by "
                         f"shutdown")
            return
        logging.info(f"Transcription of job {uid} canceled")
        self.ts_api.database.update_job_status(
            uid, JobStatus.CANCELED, completed_at=time.time())
        self._remove_audio_file()
