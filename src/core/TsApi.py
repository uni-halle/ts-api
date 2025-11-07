import logging
import os
import signal
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future
from queue import PriorityQueue, Empty
from typing import Dict, List

from pywhispercpp.utils import download_model

from packages.File import File
from core.Transcriber import Transcriber
from packages.Default import Default
from utils.database import Database, JobStatus


class TsApi:
    """Main API class with improved job handling"""
    
    def __init__(self):
        """Initialize TsAPI with ThreadPoolExecutor and event-driven queue"""
        logging.info("Starting TsAPI...")
        
        # Shutdown handling
        signal.signal(signal.SIGTERM, self.exit)
        signal.signal(signal.SIGINT, self.exit)
        
        # Database
        self.database = Database()
        
        # Thread pool for job execution
        self.executor = ThreadPoolExecutor(
            max_workers=int(os.environ.get("parallel_workers", 1)),
            thread_name_prefix="transcriber"
        )
        
        # Job tracking
        self.job_futures: Dict[str, Future] = {}
        self.cancel_events: Dict[str, threading.Event] = {}
        self.job_lock = threading.Lock()
        
        # Priority queue (in-memory, backed by database)
        self.job_queue = PriorityQueue()
        
        # Load queue from database
        self._load_queue_from_database()
        
        # Load & create default file module
        if "DefaultFileModule" not in self.database.modules:
            self.file_module = File(module_uid="DefaultFileModule")
            self.database.add_module(self.file_module)
        else:
            self.file_module = self.database.modules["DefaultFileModule"]
        
        # Load Whisper model
        model_size = os.environ.get("whisper_model", "tiny")
        if not os.path.exists(f"./data/models/{model_size}.pt"):
            logging.info("Downloading Whisper model...")
            download_model(model_size, download_dir="./data/models")
        logging.info(f"Whisper model \"{model_size}\" loaded!")
        
        # State
        self.running = True
        
        logging.info("TsAPI started!")
    
    def _load_queue_from_database(self):
        """Load queued jobs from database"""
        queue_items = self.database.load_queue()
        for priority, job_entry in queue_items:
            self.job_queue.put((priority, job_entry))
        logging.info(f"Loaded {len(queue_items)} jobs from queue")
    
    def exit(self, sig, frame):
        """Graceful shutdown with proper cleanup"""
        logging.info("Stopping TsAPI...")
        self.running = False
        
        # Cancel running jobs
        with self.job_lock:
            running_job_ids = list(self.job_futures.keys())
        
        for job_id in running_job_ids:
            logging.info(f"Canceling job {job_id} due to shutdown")
            self.cancel_job(job_id, requeue=True)
        
        # Shutdown executor gracefully
        logging.info("Waiting for jobs to finish...")
        self.executor.shutdown(wait=True, cancel_futures=True)
        
        # Final database sync
        self.database.sync()
        logging.info("TsAPI stopped!")
        sys.exit(0)
    
    def add_to_queue(self, priority: int, module_entry: Default.Entry) -> None:
        """Add a job to the queue"""
        logging.info(f"Adding job {module_entry.uid} to queue with priority {priority}")
        try:
            # Add to database
            self.database.add_job(module_entry)
            self.database.update_job_status(module_entry.uid, JobStatus.QUEUED)
            self.database.add_to_queue(module_entry.uid, priority)
            
            # Add to in-memory queue
            self.job_queue.put((priority, module_entry))
        except Exception as e:
            logging.error(f"Error adding job {module_entry.uid} to queue: {e}")
    
    def cancel_job(self, job_id: str, requeue: bool = False) -> bool:
        """
        Cancel a running or queued job
        
        Args:
            job_id: The job UID to cancel
            requeue: If True, requeue the job for later processing
        
        Returns:
            True if job was canceled, False otherwise
        """
        with self.job_lock:
            # Check if job is running
            if job_id in self.job_futures:
                future = self.job_futures[job_id]
                
                # Try to cancel if not started
                if future.cancel():
                    logging.info(f"Canceled job {job_id} before it started")
                    self._cleanup_job(job_id, requeue=requeue)
                    return True
                
                # If running, signal cancellation
                if job_id in self.cancel_events:
                    logging.info(f"Signaling cancellation for running job {job_id}")
                    self.cancel_events[job_id].set()
                    
                    if requeue:
                        # Mark for requeue
                        if job_id in self.module_entrys:
                            entry = self.database.module_entrys[job_id]
                            entry.priority = 0  # High priority for requeued jobs
                    else:
                        # Mark as canceled
                        self.database.update_job_status(job_id, JobStatus.CANCELED)
                    
                    return True
        
        return False
    
    def _cleanup_job(self, job_id: str, requeue: bool = False):
        """Clean up job resources"""
        with self.job_lock:
            if job_id in self.job_futures:
                del self.job_futures[job_id]
            if job_id in self.cancel_events:
                del self.cancel_events[job_id]
        
        # Update module counter
        if job_id in self.database.module_entrys:
            entry = self.database.module_entrys[job_id]
            entry.module.queued_or_active = max(0, entry.module.queued_or_active - 1)
            self.database.update_module(
                entry.module.module_uid,
                queued_or_active=entry.module.queued_or_active
            )
            
            if requeue:
                # Add back to queue
                self.database.update_job_status(job_id, JobStatus.QUEUED)
                self.database.add_to_queue(job_id, entry.priority)
                self.job_queue.put((entry.priority, entry))
    
    def register_job(self, entry: Default.Entry) -> Transcriber:
        """Register a job and create transcriber"""
        logging.info(f"Registering job {entry.uid}")
        
        with self.job_lock:
            # Create cancellation event
            self.cancel_events[entry.uid] = threading.Event()
        
        # Create transcriber with cancellation support
        transcriber = Transcriber(self, entry, self.cancel_events[entry.uid])
        return transcriber
    
    def unregister_job(self, entry: Default.Entry) -> None:
        """Unregister a completed job"""
        logging.info(f"Unregistering job {entry.uid}")
        self._cleanup_job(entry.uid, requeue=False)
        
        # Remove from persistent queue
        self.database.remove_from_queue(entry.uid)
    
    def start_thread(self) -> None:
        """Start background worker threads"""
        # Queue processor thread
        self.queue_thread = threading.Thread(
            target=self._queue_worker,
            name="queue_worker",
            daemon=False
        )
        self.queue_thread.start()
        
        # Persistence thread
        self.persistence_thread = threading.Thread(
            target=self._persistence_worker,
            name="persistence_worker",
            daemon=True
        )
        self.persistence_thread.start()
    
    def _queue_worker(self):
        """Event-driven queue processor (no polling delay)"""
        logging.info("Queue worker started")
        
        while self.running:
            try:
                # Block until a job is available (event-driven, no sleep needed!)
                priority, job_entry = self.job_queue.get(timeout=1)
                
                # Check if we have capacity
                with self.job_lock:
                    num_running = len(self.job_futures)
                
                parallel_workers = int(os.environ.get("parallel_workers", 1))
                
                if num_running >= parallel_workers:
                    # No capacity, put back in queue
                    self.job_queue.put((priority, job_entry))
                    time.sleep(0.1)  # Small delay to avoid busy waiting
                    continue
                
                # Submit job to thread pool
                logging.info(f"Starting job {job_entry.uid} from queue")
                
                # Create future
                future = self.executor.submit(self._process_job, job_entry)
                
                with self.job_lock:
                    self.job_futures[job_entry.uid] = future
                
                # Add callback for completion
                future.add_done_callback(
                    lambda f, uid=job_entry.uid: self._on_job_complete(uid, f)
                )
                
            except Empty:
                # Timeout reached, loop continues
                continue
            except Exception as e:
                logging.error(f"Error in queue worker: {e}")
        
        logging.info("Queue worker stopped")
    
    def _process_job(self, job_entry: Default.Entry):
        """Process a single job"""
        try:
            # Preprocessing
            logging.info(f"Preprocessing job {job_entry.uid}")
            job_entry.preprocessing()
            self.database.update_job_status(job_entry.uid, JobStatus.PREPARED)
            
            # Check cancellation
            cancel_event = self.cancel_events.get(job_entry.uid)
            if cancel_event and cancel_event.is_set():
                logging.info(f"Job {job_entry.uid} canceled during preprocessing")
                return
            
            # Start transcription
            transcriber = self.register_job(job_entry)
            transcriber.transcribe()
            
        except Exception as e:
            logging.error(f"Error processing job {job_entry.uid}: {e}")
            self.database.update_job_status(
                job_entry.uid,
                JobStatus.FAILED,
                error_message=str(e)
            )
    
    def _on_job_complete(self, job_id: str, future: Future):
        """Callback when job completes"""
        try:
            # Check if job had an exception
            exception = future.exception()
            if exception:
                logging.error(f"Job {job_id} failed with exception: {exception}")
                self.database.update_job_status(
                    job_id,
                    JobStatus.FAILED,
                    error_message=str(exception),
                    completed_at=time.time()
                )
        except Exception as e:
            logging.error(f"Error in job completion callback: {e}")
        finally:
            # Always cleanup
            if job_id in self.database.module_entrys:
                self.unregister_job(self.database.module_entrys[job_id])
    
    def _persistence_worker(self):
        """Periodic database sync and health monitoring"""
        logging.info("Persistence worker started")
        
        while self.running:
            time.sleep(30)  # Sync every 30 seconds
            
            try:
                # Force WAL checkpoint
                self.database.sync()
                
                # Log system health
                stats = self.database.get_stats()
                with self.job_lock:
                    stats['running_jobs'] = len(self.job_futures)
                
                logging.info(f"System health: {stats}")
                
            except Exception as e:
                logging.error(f"Error in persistence worker: {e}")
        
        logging.info("Persistence worker stopped")
    
    @property
    def running_jobs(self) -> List[Default.Entry]:
        """Get list of currently running jobs (for compatibility with app.py)"""
        with self.job_lock:
            job_ids = list(self.job_futures.keys())
        
        return [
            self.database.module_entrys[job_id]
            for job_id in job_ids
            if job_id in self.database.module_entrys
        ]
