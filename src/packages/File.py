import logging

from werkzeug.datastructures import FileStorage

import database
import util
from Default import Default

# noinspection PyMethodOverriding
class File(Default):
    """
    Eine Implementierung des Default-Moduls für Dateien.

    :var module_uid: Eindeutige ID des Moduls.
    :var entrys: Dictionary mit den Einträgen des Moduls.
    """

    def __init__(self) -> None:
        """
        Initialisiert ein Default-Modul mit einer eindeutigen ID und einem leeren Dictionary für Einträge.
        """
        super().__init__()
        logging.debug(f"Created File Module with id {self.module_uid}.")

    # noinspection PyMethodOverriding
    class Entry(Default.Entry):
        """
        Repräsentiert einen einzelnen Eintrag im Dateien-Modul.

        :var uid: Die eindeutige ID des Eintrags.
        """

        def __init__(self, module, uid: str) -> None:
            """
            Initialisiert einen neuen Dateien Moduleintrag.

            :param module: Die zugehörige Default-Modulinstanz.
            :param uid: Die eindeutige ID des Eintrags.
            """
            super().__init__(module, uid)
            logging.debug(f"Created File Module entry with id {self.uid}.")

        def queuing(self, file: FileStorage) -> bool:
            """
            Speichert die Datei und fügt einen Job zur Warteschlange hinzu.

            :param file: Die Datei, die gespeichert werden soll.
            :return: True, wenn der Job erfolgreich hinzugefügt wurde.
            """
            if util.save_file(file, self.uid):
                super().queuing(self)
                logging.debug(f"Queued File Module entry with id {self.uid}.")
                return True
            return False

        def preprocessing(self) -> None:
            """
            Abstrakte Methode zur Vorverarbeitung von Daten. Wird hier nicht benötigt.
            """
            pass

