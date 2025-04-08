import logging

from werkzeug.datastructures import FileStorage

import utils
from packages.Default import Default


# noinspection PyMethodOverriding
class File(Default):
    """
    Eine Implementierung des Default-Moduls für Dateien.

    :var module_uid: Eindeutige ID des Moduls.
    :var entrys: Dictionary mit den Einträgen des Moduls.
    """

    def __init__(self, module_type: str = "File.File", **kwargs) -> None:
        """
        Initialisiert ein Default-Modul mit einer eindeutigen ID und einem
        leeren Dictionary für Einträge.
        """
        super().__init__(module_type, **kwargs)
        logging.debug(f"Created File Module with id {self.module_uid}.")

    # noinspection PyMethodOverriding
    class Entry(Default.Entry):
        """
        Repräsentiert einen einzelnen Eintrag im Dateien-Modul.

        :var uid: Die eindeutige ID des Eintrags.
        """

        def __init__(self, module, uid: str, priority: int, **kwargs) -> None:
            """
            Initialisiert einen neuen Dateien Moduleintrag.

            :param module: Die zugehörige Default-Modulinstanz.
            :param uid: Die eindeutige ID des Eintrags.
            """
            super().__init__(module, uid, priority, **kwargs)
            logging.debug(f"Created File Module entry with id {self.uid}.")

        def queuing(self, ts_api, file: FileStorage) -> bool:
            """
            Speichert die Datei und fügt einen Job zur Warteschlange hinzu.

            :param ts_api: Die aktuelle TsAPI Instanz.
            :param file: Die Datei, die gespeichert werden soll.
            :return: True, wenn der Job erfolgreich hinzugefügt wurde.
            """
            if utils.util.save_file(file, self.uid):
                super().queuing(ts_api)
                logging.debug(f"Queued File Module entry with id {self.uid}.")
                return True
            return False

        def preprocessing(self) -> None:
            """
            Abstrakte Methode zur Vorverarbeitung von Daten.
            Wird hier nicht benötigt.
            """
            pass
