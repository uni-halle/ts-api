import logging
import os
import time

import requests

from core.TsApi import TsApi
from packages.Default import Default, JobCanceled

DOWNLOAD_CHUNK_SIZE = 1024 * 1024


class _RetryableDownloadError(Exception):
    """A download error that may go away when trying again."""


# noinspection PyMethodOverriding
class Opencast(Default):
    """
    Eine Implementierung des Default-Moduls für Opencast.

    :var module_uid: Eindeutige ID des Moduls.
    :var queued_or_active: Anzahl der aktiven oder gequeten Einträge
    :var max_queue_length: Maximale Anzahl von Einträgen in der Warteschlange.
    """

    def __init__(self, module_type="Opencast.Opencast", max_queue_length:
                 int = 10, **kwargs) -> None:
        """
        Initialisiert ein Opencast-Modul mit einer maximalen
        Warteschlangenlänge.

        :param max_queue_length: Die maximale Anzahl an Jobs,
        die verarbeitet werden können.
        """
        super().__init__(module_type, **kwargs)
        self.max_queue_length: int = int(max_queue_length)
        logging.debug(f"Created Opencast Module with id {self.module_uid}.")

    # noinspection PyMethodOverriding
    class Entry(Default.Entry):
        """
        Repräsentiert einen einzelnen Eintrag im Opencast-Modul.

        :var module: Die zugehörige Opencast-Modulinstanz.
        :var uid: Die eindeutige ID des Eintrags.
        :var link: URL zur Datei.
        :var initial_prompt: Initiale Beschreibung oder Titel.
        """

        def __init__(self,
                     module,
                     uid: str,
                     link: str,
                     priority: int = 1,
                     **kwargs) -> None:
            """
            Initialisiert einen neuen Opencast Moduleintrag.

            :param module: Die zugehörige Modulinstanz.
            :param uid: Die eindeutige ID des Eintrags.
            :param link: Die URL zur Datei.
            :param initial_prompt: Die initiale Beschreibung oder der Titel
            des Eintrags.
            """
            super().__init__(module, uid, priority, **kwargs)
            self.module: Opencast = module
            self.link: str = link
            logging.debug(f"Created Opencast Module entry with id {self.uid}.")

        def queuing(self, ts_api: TsApi) -> bool:
            """
            Fügt einen Job zur Warteschlange hinzu, falls noch Platz
            vorhanden ist.

            :param ts_api: Die aktuelle TsAPI Instanz.
            :return: `True`, wenn der Job hinzugefügt wurde, `False`,
            wenn die Warteschlange voll ist.
            """
            if self.module.queued_or_active < self.module.max_queue_length:
                super().queuing(ts_api)
                logging.debug(f"Queued Opencast Module entry with id"
                              f" {self.uid}.")
                return True
            logging.debug(f"Refused to queue Opencast Module entry with id"
                          f" {self.uid} because of max queue length.")
            return False

        def preprocessing(self, cancel_event=None) -> None:
            """
            Lädt die Datei von der angegebenen URL herunter und speichert
            sie lokal. Vorübergehende Fehler (Verbindungsfehler, Timeouts,
            HTTP 429/5xx) werden mehrfach versucht.

            :param cancel_event: Wird es gesetzt, bricht der Download ab.
            :raises JobCanceled: Falls der Job abgebrochen wurde.
            :raises Exception: Falls der Download fehlschlägt.
            """
            retries = int(os.environ.get("download_retries", 2))
            attempt = 0
            while True:
                try:
                    self._download(cancel_event)
                    return
                except _RetryableDownloadError as e:
                    attempt += 1
                    if attempt > retries:
                        raise Exception(f"Failed to download file: {e}")
                    delay = min(2 ** attempt, 30)
                    logging.warning(f"Download for job id {self.uid} "
                                    f"failed ({e}), retrying in {delay}s "
                                    f"({attempt}/{retries}).")
                    if cancel_event and cancel_event.wait(delay):
                        raise JobCanceled()
                    if cancel_event is None:
                        time.sleep(delay)

        def _download(self, cancel_event=None) -> None:
            """
            Streamt die Datei auf die Festplatte, ohne sie vollständig in
            den Arbeitsspeicher zu laden.
            """
            connect_timeout = float(
                os.environ.get("download_connect_timeout", 10))
            read_timeout = float(os.environ.get("download_read_timeout", 60))
            max_duration = float(os.environ.get("download_timeout", 3600))
            deadline = time.monotonic() + max_duration

            target = os.path.join(os.getcwd(), "data", "audioInput",
                                  self.uid)
            part = target + ".part"
            logging.debug(f"Downloading file for job id {self.uid}...")
            try:
                try:
                    with requests.get(self.link, stream=True,
                                      timeout=(connect_timeout,
                                               read_timeout)) as response:
                        if (response.status_code == 429
                                or response.status_code >= 500):
                            raise _RetryableDownloadError(
                                f"HTTP {response.status_code}")
                        if response.status_code != 200:
                            raise Exception(f"Failed to download file: HTTP "
                                            f"{response.status_code}")
                        with open(part, "wb") as file:
                            for chunk in response.iter_content(
                                    chunk_size=DOWNLOAD_CHUNK_SIZE):
                                if cancel_event and cancel_event.is_set():
                                    raise JobCanceled()
                                if time.monotonic() > deadline:
                                    raise Exception(
                                        f"Failed to download file: not "
                                        f"finished after {max_duration:g}s")
                                file.write(chunk)
                except (requests.ConnectionError, requests.Timeout,
                        requests.exceptions.ChunkedEncodingError) as e:
                    raise _RetryableDownloadError(str(e))
                os.replace(part, target)
            finally:
                if os.path.exists(part):
                    os.remove(part)
            logging.debug(f"Downloaded file for job id {self.uid}.")
