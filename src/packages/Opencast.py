import logging
import uuid
import io
from typing import Dict

from werkzeug.datastructures import FileStorage

import database
import util
import requests
from requests import request
from packages.Default import Default

# noinspection PyMethodOverriding
class Opencast(Default):
    """
    Eine Implementierung des Default-Moduls für Opencast.

    :var module_uid: Eindeutige ID des Moduls.
    :var entrys: Dictionary mit den Einträgen des Moduls.
    :var max_queue_length: Maximale Anzahl von Einträgen in der Warteschlange.
    """

    def __init__(self, max_queue_length: int) -> None:
        """
        Initialisiert ein Opencast-Modul mit einer maximalen Warteschlangenlänge.

        :param max_queue_length: Die maximale Anzahl an Jobs, die verarbeitet werden können.
        """
        super().__init__()
        self.max_queue_length: int = max_queue_length
        logging.debug(f"Created Opencast Module with id {self.module_uid}.")

    def create(self, uid: str, link: str, initial_prompt: str):
        """
        Erstellt einen neuen Opencast Moduleintrag.

        :param uid: Die eindeutige ID des Eintrags.
        :param link: Die URL zur Datei.
        :param initial_prompt: Die initiale Beschreibung oder der Titel des Eintrags.
        :return: Der erstellte Moduleintrag.
        """
        module_entry: Opencast.Entry = Opencast.Entry(self, uid, link, initial_prompt)
        self.entrys[uid] = module_entry
        return module_entry

    # noinspection PyMethodOverriding
    class Entry(Default.Entry):
        """
        Repräsentiert einen einzelnen Eintrag im Opencast-Modul.

        :var module: Die zugehörige Opencast-Modulinstanz.
        :var uid: Die eindeutige ID des Eintrags.
        :var link: URL zur Datei.
        :var initial_prompt: Initiale Beschreibung oder Titel.
        """

        def __init__(self, module, uid: str, link: str, initial_prompt: str) -> None:
            """
            Initialisiert einen neuen Opencast Moduleintrag.

            :param module: Die zugehörige Modulinstanz.
            :param uid: Die eindeutige ID des Eintrags.
            :param link: Die URL zur Datei.
            :param initial_prompt: Die initiale Beschreibung oder der Titel des Eintrags.
            """
            super().__init__(module, uid)
            self.module: Opencast = module
            self.link: str = link
            self.initial_prompt: str = initial_prompt
            logging.debug(f"Created Opencast Module entry with id {self.uid}.")

        def queuing(self) -> bool:
            """
            Fügt einen Job zur Warteschlange hinzu, falls noch Platz vorhanden ist.

            :return: `True`, wenn der Job hinzugefügt wurde, `False`, wenn die Warteschlange voll ist.
            """
            if len(self.module.entrys) < self.module.max_queue_length:
                database.add_job(self)
                return True
            return False

        def preprocessing(self) -> None:
            """
            Lädt die Datei von der angegebenen URL herunter und speichert sie lokal.
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
            util.save_file(file, self.uid)
            logging.debug(f"Downloaded file for job id {self.uid}.")
