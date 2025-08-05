import logging
import io

from werkzeug.datastructures import FileStorage

import utils
import requests
from requests import request

from core.TsApi import TsApi
from packages.Default import Default


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

        def preprocessing(self) -> None:
            """
            Lädt die Datei von der angegebenen URL herunter und speichert
            sie lokal.
            Falls der Download fehlschlägt, wird eine Exception ausgelöst.

            :raises Exception: Falls der Download fehlschlägt.
            """
            logging.debug(f"Downloading file for job id {self.uid}...")
            session: request = requests.Session()
            response = session.get(self.link)
            if response.status_code != 200:
                raise Exception("Failed to download file.")
            file = FileStorage(
                stream=io.BytesIO(response.content),
                filename=self.uid,
                content_length=response.headers.get("Content-Length"),
                content_type=response.headers.get("Content-Type")
            )
            utils.util.save_file(file, self.uid)
            logging.debug(f"Downloaded file for job id {self.uid}.")
