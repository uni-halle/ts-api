import json
import logging
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from enum import IntEnum
from pydoc import locate
from typing import Dict, Optional, Any
import numpy as np

from packages.Default import Default


class JobStatus(IntEnum):
    """Job status enumeration"""
    QUEUED = 0
    PREPARED = 1
    PROCESSING = 2
    COMPLETED = 3
    FAILED = 4
    CANCELED = 5


# Columns that may be changed through change_job_entry/update_job_status
JOB_COLUMNS = {
    "status", "priority", "started_at", "completed_at", "whisper_result",
    "whisper_language", "whisper_model", "initial_prompt", "error_message",
    "link", "vad_segments",
}
# Columns stored as JSON
JSON_COLUMNS = {"whisper_result", "vad_segments"}
MODULE_COLUMNS = {"queued_or_active"}
# Module attributes that have their own column, everything else is stored
# in the config column and passed back to the constructor on load
MODULE_BASE_ATTRIBUTES = {"module_uid", "module_type", "queued_or_active"}


class Database:
    """SQLite-based database for job and module persistence"""

    def __init__(self, db_path: str = "./data/tsapi.db"):
        self.db_path = db_path
        self.modules: Dict[str, Default] = {}
        self.module_entrys: Dict[str, Default.Entry] = {}
        self.lock = threading.RLock()

        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

        self._init_schema()
        self._load_from_database()

    def _init_schema(self):
        """Create database tables if they don't exist"""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    uid TEXT PRIMARY KEY,
                    module_type TEXT NOT NULL,
                    module_uid TEXT NOT NULL,
                    status INTEGER NOT NULL,
                    priority INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    started_at REAL,
                    completed_at REAL,
                    whisper_result TEXT,
                    whisper_language TEXT,
                    whisper_model TEXT,
                    initial_prompt TEXT,
                    error_message TEXT,
                    link TEXT,
                    vad_segments TEXT,
                    updated_at REAL NOT NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS modules (
                    module_uid TEXT PRIMARY KEY,
                    module_type TEXT NOT NULL,
                    queued_or_active INTEGER NOT NULL DEFAULT 0,
                    config TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)

            # Queue table (for persistence)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_uid TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    added_at REAL NOT NULL,
                    FOREIGN KEY (job_uid) REFERENCES jobs(uid)
                )
            """)

            # Columns added after the first SQLite version
            self._add_missing_columns(conn, "jobs", {"link": "TEXT",
                                                     "vad_segments": "TEXT"})
            self._add_missing_columns(conn, "modules", {"config": "TEXT"})

            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status "
                         "ON jobs(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_priority "
                         "ON jobs(priority)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_queue_priority "
                         "ON queue(priority, added_at)")

            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")

            logging.info("Database schema initialized")

    @staticmethod
    def _add_missing_columns(conn, table: str, columns: Dict[str, str]):
        existing = {row["name"] for row in
                    conn.execute(f"PRAGMA table_info({table})")}
        for name, column_type in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} "
                             f"ADD COLUMN {name} {column_type}")

    @contextmanager
    def _get_connection(self):
        """Get a database connection with proper error handling"""
        conn = sqlite3.connect(self.db_path, timeout=10.0,
                               check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logging.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def _load_from_database(self):
        """Load modules and jobs from database into memory"""
        with self._get_connection() as conn:
            for row in conn.execute("SELECT * FROM modules"):
                try:
                    module_type_class = locate(
                        f"packages.{row['module_type']}")
                    if not module_type_class:
                        logging.error(f"Unknown module type "
                                      f"{row['module_type']}")
                        continue
                    config = json.loads(row["config"]) \
                        if row["config"] else {}
                    module = module_type_class(
                        module_uid=row['module_uid'],
                        queued_or_active=row['queued_or_active'],
                        **config
                    )
                    self.modules[row['module_uid']] = module
                    logging.debug(f"Loaded module {row['module_uid']}")
                except Exception as e:
                    logging.error(f"Failed to load module "
                                  f"{row['module_uid']}: {e}")

            for row in conn.execute("SELECT * FROM jobs"):
                try:
                    module = self.modules.get(row['module_uid'])
                    if not module:
                        logging.warning(f"Module {row['module_uid']} not "
                                        f"found for job {row['uid']}")
                        continue

                    entry_class = type(module).Entry
                    extra = {}
                    if row["link"] is not None:
                        extra["link"] = row["link"]
                    entry = entry_class(
                        module=module,
                        uid=row['uid'],
                        priority=row['priority'],
                        time=row['created_at'],
                        status=row['status'],
                        initial_prompt=row['initial_prompt'],
                        whisper_result=self._load_json(
                            row['whisper_result']),
                        whisper_language=row['whisper_language'],
                        whisper_model=row['whisper_model'],
                        vad_segments=self._load_json(row['vad_segments']),
                        **extra
                    )
                    entry.error_message = row["error_message"]
                    self.module_entrys[row['uid']] = entry
                    logging.debug(f"Loaded job {row['uid']}")
                except Exception as e:
                    logging.error(f"Failed to load job {row['uid']}: {e}")

        logging.info(f"Loaded {len(self.modules)} modules and "
                     f"{len(self.module_entrys)} jobs from database")

    @staticmethod
    def _load_json(value):
        if not value:
            return None
        try:
            return json.loads(value)
        except ValueError:
            return value

    def _dump_value(self, column: str, value):
        if column in JSON_COLUMNS and value is not None:
            return json.dumps(value, default=self._safe_serialize)
        return value

    def add_module(self, module: Default) -> bool:
        """Add a module to the database"""
        try:
            now = time.time()
            config = {key: value for key, value in vars(module).items()
                      if key not in MODULE_BASE_ATTRIBUTES}
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO modules
                    (module_uid, module_type, queued_or_active, config,
                     created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (module.module_uid, module.module_type,
                      module.queued_or_active, json.dumps(config), now, now))

            self.modules[module.module_uid] = module
            logging.debug(f"Added module {module.module_uid}")
            return True
        except Exception as e:
            logging.error(f"Failed to add module: {e}")
            return False

    def update_module(self, module_uid: str, **kwargs):
        """Update module fields"""
        unknown = set(kwargs) - MODULE_COLUMNS
        if unknown:
            raise ValueError(f"Unknown module columns: {unknown}")
        try:
            updates = [f"{key} = ?" for key in kwargs]
            values = list(kwargs.values())
            if not updates:
                return True

            updates.append("updated_at = ?")
            values.append(time.time())
            values.append(module_uid)

            with self._get_connection() as conn:
                conn.execute(
                    f"UPDATE modules SET {', '.join(updates)} "
                    f"WHERE module_uid = ?",
                    values
                )

            if module_uid in self.modules:
                for key, value in kwargs.items():
                    setattr(self.modules[module_uid], key, value)

            return True
        except Exception as e:
            logging.error(f"Failed to update module: {e}")
            return False

    def add_job(self, module_entry: Default.Entry) -> bool:
        """Add a job to the database"""
        try:
            now = time.time()
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO jobs
                    (uid, module_type, module_uid, status, priority,
                     created_at, started_at, completed_at, whisper_result,
                     whisper_language, whisper_model, initial_prompt,
                     error_message, link, vad_segments, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    module_entry.uid,
                    module_entry.module.module_type,
                    module_entry.module.module_uid,
                    int(module_entry.status)
                    if module_entry.status is not None
                    else int(JobStatus.QUEUED),
                    module_entry.priority,
                    module_entry.time,
                    None,  # started_at
                    None,  # completed_at
                    self._dump_value(
                        "whisper_result",
                        getattr(module_entry, 'whisper_result', None)),
                    getattr(module_entry, 'whisper_language', None),
                    getattr(module_entry, 'whisper_model', None),
                    getattr(module_entry, 'initial_prompt', None),
                    None,  # error_message
                    getattr(module_entry, 'link', None),
                    self._dump_value(
                        "vad_segments",
                        getattr(module_entry, 'vad_segments', None)),
                    now
                ))

            self.module_entrys[module_entry.uid] = module_entry
            logging.debug(f"Added job {module_entry.uid}")
            return True
        except Exception as e:
            logging.error(f"Failed to add job: {e}")
            return False

    def load_job(self, uid: str) -> Optional[Default.Entry]:
        """Load a job by UID"""
        return self.module_entrys.get(uid)

    def exists_job(self, uid: str) -> bool:
        """Check if a job exists"""
        return uid in self.module_entrys

    def delete_job(self, uid: str) -> bool:
        """Delete a job from the database"""
        try:
            with self.lock:
                with self._get_connection() as conn:
                    conn.execute("DELETE FROM jobs WHERE uid = ?", (uid,))
                    conn.execute("DELETE FROM queue WHERE job_uid = ?",
                                 (uid,))
                self.module_entrys.pop(uid, None)

            logging.debug(f"Deleted job {uid}")
            return True
        except Exception as e:
            logging.error(f"Failed to delete job {uid}: {e}")
            return False

    def change_job_entry(self, uid: str, entry: str, value: Any) -> bool:
        """Change a job entry field"""
        if entry not in JOB_COLUMNS:
            raise ValueError(f"Unknown job column: {entry}")
        try:
            with self.lock:
                if uid not in self.module_entrys:
                    # The job has been deleted in the meantime
                    logging.debug(f"Not updating {entry} of job {uid}: "
                                  f"job not found")
                    return False
                setattr(self.module_entrys[uid], entry, value)

                with self._get_connection() as conn:
                    conn.execute(
                        f"UPDATE jobs SET {entry} = ?, updated_at = ? "
                        f"WHERE uid = ?",
                        (self._dump_value(entry, value), time.time(), uid)
                    )

            logging.debug(f"Updated job {uid}: {entry}")
            return True
        except Exception as e:
            logging.error(f"Failed to update job {uid}: {e}")
            return False

    def update_job_status(self, uid: str, status: JobStatus, **kwargs):
        """Update job status and other fields atomically"""
        unknown = set(kwargs) - JOB_COLUMNS
        if unknown:
            raise ValueError(f"Unknown job columns: {unknown}")
        try:
            with self.lock:
                if uid not in self.module_entrys:
                    logging.debug(f"Not updating status of job {uid}: "
                                  f"job not found")
                    return False

                updates = ["status = ?", "updated_at = ?"]
                values = [int(status), time.time()]
                for key, value in kwargs.items():
                    updates.append(f"{key} = ?")
                    values.append(self._dump_value(key, value))
                values.append(uid)

                with self._get_connection() as conn:
                    conn.execute(
                        f"UPDATE jobs SET {', '.join(updates)} "
                        f"WHERE uid = ?",
                        values
                    )

                entry = self.module_entrys[uid]
                entry.status = status
                for key, value in kwargs.items():
                    setattr(entry, key, value)

            return True
        except Exception as e:
            logging.error(f"Failed to update job status: {e}")
            return False

    def add_to_queue(self, job_uid: str, priority: int):
        """Add a job to the persistent queue"""
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM queue WHERE job_uid = ?",
                             (job_uid,))
                conn.execute("""
                    INSERT INTO queue (job_uid, priority, added_at)
                    VALUES (?, ?, ?)
                """, (job_uid, priority, time.time()))
            return True
        except Exception as e:
            logging.error(f"Failed to add to queue: {e}")
            return False

    def remove_from_queue(self, job_uid: str):
        """Remove a job from the persistent queue"""
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM queue WHERE job_uid = ?",
                             (job_uid,))
            return True
        except Exception as e:
            logging.error(f"Failed to remove from queue: {e}")
            return False

    def load_queue(self):
        """
        Load the queue from database
        :return: list of (priority, job_entry) tuples
        """
        queue_items = []
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT job_uid, priority FROM queue
                    ORDER BY priority ASC, added_at ASC
                """)
                for row in cursor:
                    job_entry = self.module_entrys.get(row['job_uid'])
                    if job_entry:
                        queue_items.append((row['priority'], job_entry))
                    else:
                        logging.warning(f"Queue references missing job "
                                        f"{row['job_uid']}")
        except Exception as e:
            logging.error(f"Failed to load queue: {e}")

        return queue_items

    def sync(self):
        """Force WAL checkpoint and sync to disk"""
        try:
            with self._get_connection() as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            logging.debug("Database synced to disk")
        except Exception as e:
            logging.error(f"Failed to sync database: {e}")

    def get_stats(self) -> Dict[str, int]:
        """Get database statistics"""
        stats = {}
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT status, COUNT(*) as count "
                                      "FROM jobs GROUP BY status")
                for row in cursor:
                    status_name = JobStatus(row['status']).name
                    stats[f"jobs_{status_name.lower()}"] = row['count']

                cursor = conn.execute("SELECT COUNT(*) as count FROM queue")
                stats['queue_length'] = cursor.fetchone()['count']
        except Exception as e:
            logging.error(f"Failed to get stats: {e}")

        return stats

    @staticmethod
    def _safe_serialize(o):
        """Safely serialize objects for JSON"""
        if hasattr(o, '__dict__'):
            return o.__dict__
        elif isinstance(o, (np.float32, np.float64)):
            return float(o)
        elif isinstance(o, (np.int32, np.int64)):
            return int(o)
        elif isinstance(o, np.ndarray):
            return o.tolist()
        else:
            return str(o)

    def save_database(self) -> bool:
        """
        Legacy method for compatibility.
        With SQLite everything is persisted immediately, this just forces a
        WAL checkpoint.
        """
        self.sync()
        return True
