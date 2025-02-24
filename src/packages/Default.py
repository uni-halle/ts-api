import time
import uuid

from abc import ABC, abstractmethod
from typing import Dict, Any


# noinspection PyMethodOverriding
class Default(ABC):
    """
    Abstrakte Basisklasse für Module.

    :var module_uid: Eindeutige ID des Moduls.
    :var entrys: Dictionary mit den Einträgen des Moduls.
    """

    def __init__(self) -> None:
        """
        Initialisiert ein Default-Modul mit einer eindeutigen ID und einem leeren Dictionary für Einträge.
        """
        self.module_uid: str = str(uuid.uuid4())
        self.entrys: Dict[str, Default.Entry] = {}

    @abstractmethod
    def create(self, uid: str, *args: Any):
        """
        Erstellt einen neuen Moduleintrag und speichert ihn im Dictionary.

        :param uid: Die eindeutige ID des Eintrags.
        :return: Der erstellte Moduleintrag.
        """
        pass

    # noinspection PyMethodOverriding
    class Entry(ABC):
        """
        Abstrakte Basisklasse für Moduleinträge.

        :var time: Die erstellungs Zeit
        :var module: Die zugehörige Modulinstanz.
        :var uid: Die eindeutige ID des Eintrags.
        """

        def __init__(self, module, uid: str) -> None:
            """
            Initialisiert einen neuen Moduleintrag und verknüpft ihn mit dem Modul.

            :param uid: Die eindeutige ID des Eintrags.
            """
            self.time: float = time.time()
            self.module: Default = module
            self.uid: str = uid

        def __lt__(self, other) -> bool:
            return self.time < other.time

        def __gt__(self, other) -> bool:
            return self.time > other.time

        def __eq__(self, other) -> bool:
            return self.time == other.time

        @abstractmethod
        def queuing(self) -> bool:
            """
            Abstrakte Methode zum queuen des Eintrags. Kann von Unterklassen implementiert werden.
            """
            pass

        @abstractmethod
        def preprocessing(self) -> None:
            """
            Abstrakte Methode zur Vorverarbeitung von Daten. Kann von Unterklassen implementiert werden.
            """
            pass
