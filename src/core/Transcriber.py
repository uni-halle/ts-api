import logging
import threading
import os
import time
import multiprocessing
from multiprocessing import Process, Queue

from packages.Default import Default
from pywhispercpp.model import Model
from utils.database import JobStatus


def _run_transcription_in_process(file_path, model_size, n_threads, language, initial_prompt, result_queue):
    """
    Run transcription in a separate process so it can be terminated
    This is necessary because Whisper C++ transcription cannot be interrupted from Python
    """
    try:
        # Load model in subprocess
        model = Model(
            model_size,
            models_dir="./data/models",
            n_threads=n_threads
        )
        
        # Prepare kwargs
        kwargs = {"language": language}
        if initial_prompt:
            kwargs["initial_prompt"] = initial_prompt
        
        # Transcribe
        result = model.transcribe(file_path, **kwargs)
        
        # Send result back
        result_queue.put({"success": True, "result": result})
    except Exception as e:
        result_queue.put({"success": False, "error": str(e)})


class Transcriber:
    """Transcriber with true cancellation support via multiprocessing"""
    
    def __init__(self, ts_api, module_entry: Default.Entry, cancel_event: threading.Event):
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
            logging.info(f"Starting transcription for job {self.module_entry.uid}")
            
            # Check cancellation before starting
            if self.cancel_event.is_set():
                logging.info(f"Job {self.module_entry.uid} canceled before transcription")
                self._handle_cancellation()
                return
            
            # Update status to processing
            self.ts_api.database.update_job_status(
                self.module_entry.uid,
                JobStatus.PROCESSING,
                started_at=time.time()
            )
            
            # Load Whisper model for language detection
            model_size = os.environ.get("whisper_model", "tiny")
            n_threads = int(os.environ.get("whisper_cpu_threads", 4))
            
            model = Model(
                model_size,
                models_dir="./data/models",
                n_threads=n_threads
            )
            
            self.ts_api.database.change_job_entry(
                self.module_entry.uid,
                "whisper_model",
                model_size
            )
            
            # Check cancellation after model loading
            if self.cancel_event.is_set():
                logging.info(f"Job {self.module_entry.uid} canceled after model loading")
                self._handle_cancellation()
                return
            
            # Detect language
            logging.info(f"Detecting language for job {self.module_entry.uid}")
            most_likely, probs = model.auto_detect_language(
                self.file_path,
                offset_ms=5000
            )
            self.whisper_language = most_likely[0]
            
            self.ts_api.database.change_job_entry(
                self.module_entry.uid,
                "whisper_language",
                self.whisper_language
            )
            
            logging.info(f"Detected language: {self.whisper_language} for job {self.module_entry.uid}")
            
            # Check cancellation after language detection
            if self.cancel_event.is_set():
                logging.info(f"Job {self.module_entry.uid} canceled after language detection")
                self._handle_cancellation()
                return
            
            # Prepare initial prompt
            initial_prompt = None
            if (hasattr(self.module_entry, "initial_prompt")
                    and self.module_entry.initial_prompt):
                initial_prompt = self.module_entry.initial_prompt
            
            # Start transcription in a separate process
            logging.info(f"Starting Whisper transcription in subprocess for job {self.module_entry.uid}")
            
            result_queue = Queue()
            self.transcription_process = Process(
                target=_run_transcription_in_process,
                args=(self.file_path, model_size, n_threads, self.whisper_language, initial_prompt, result_queue)
            )
            self.transcription_process.start()
            
            # Poll for completion or cancellation
            while self.transcription_process.is_alive():
                if self.cancel_event.is_set():
                    logging.info(f"Cancellation requested for job {self.module_entry.uid} - terminating process")
                    self.transcription_process.terminate()
                    self.transcription_process.join(timeout=5)
                    
                    if self.transcription_process.is_alive():
                        logging.warning(f"Process didn't terminate gracefully, killing it")
                        self.transcription_process.kill()
                        self.transcription_process.join()
                    
                    self._handle_cancellation()
                    return
                
                # Check every 0.5 seconds
                time.sleep(0.5)
            
            # Process completed, get result
            self.transcription_process.join()
            
            # Check if process was successful
            if not result_queue.empty():
                result_data = result_queue.get()
                
                if result_data["success"]:
                    result = result_data["result"]
                    
                    # Store results
                    self.whisper_result = result
                    self.ts_api.database.update_job_status(
                        self.module_entry.uid,
                        JobStatus.COMPLETED,
                        whisper_result=result,
                        completed_at=time.time()
                    )
                    
                    # Clean up audio file
                    if os.path.exists(self.file_path):
                        os.remove(self.file_path)
                        logging.debug(f"Removed audio file for job {self.module_entry.uid}")
                    
                    logging.info(f"Successfully completed job {self.module_entry.uid}")
                else:
                    raise Exception(result_data["error"])
            else:
                # Process exited without result
                raise Exception("Transcription process exited without result")
            
        except Exception as e:
            logging.error(f"Error transcribing job {self.module_entry.uid}: {e}")
            self.ts_api.database.update_job_status(
                self.module_entry.uid,
                JobStatus.FAILED,
                error_message=str(e),
                completed_at=time.time()
            )
            
            # Clean up audio file on error
            if os.path.exists(self.file_path):
                try:
                    os.remove(self.file_path)
                except:
                    pass
            
            # Clean up process if still running
            if self.transcription_process and self.transcription_process.is_alive():
                self.transcription_process.terminate()
                self.transcription_process.join(timeout=2)
    
    def _handle_cancellation(self):
        """Handle job cancellation cleanly"""
        logging.info(f"Handling cancellation for job {self.module_entry.uid}")
        
        # Update status
        self.ts_api.database.update_job_status(
            self.module_entry.uid,
            JobStatus.CANCELED,
            completed_at=time.time()
        )
        
        # Clean up audio file
        if os.path.exists(self.file_path):
            try:
                os.remove(self.file_path)
                logging.debug(f"Removed audio file for canceled job {self.module_entry.uid}")
            except Exception as e:
                logging.error(f"Failed to remove audio file: {e}")
    
    # Keep old method for backward compatibility (though it's not used anymore)
    def start_thread(self):
        """
        Deprecated: Jobs are now submitted to ThreadPoolExecutor
        This method is kept for compatibility but should not be called
        """
        logging.warning("start_thread() is deprecated and should not be called")
        whisper_thread = threading.Thread(
            target=self.transcribe,
            daemon=True
        )
        whisper_thread.start()
