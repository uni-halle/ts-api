import time
import uuid

from abc import ABC, abstractmethod


# noinspection PyMethodOverriding
class Default(ABC):
    """
    Abstrakte Basisklasse für Module.

    :var module_uid: Eindeutige ID des Moduls.
    :var queued_or_active: Anzahl der aktiven oder gequeten Einträge
    """

    @abstractmethod
    def __init__(self, module_type: str, module_uid:
                 str = str(uuid.uuid4()), queued_or_active=0) -> None:
        """
        Initialisiert ein Default-Modul mit einer eindeutigen ID und einem
        leeren Dictionary für Einträge.
        """
        self.module_type: str = module_type
        self.module_uid: str = module_uid
        self.queued_or_active: int = queued_or_active

    # noinspection PyMethodOverriding
    class Entry(ABC):
        """
        Abstrakte Basisklasse für Moduleinträge.

        :var time: Die Erstellung Zeit
        :var module: Die zugehörige Modulinstanz.
        :var uid: Die eindeutige ID des Eintrags.
        """

        @abstractmethod
        def __init__(self,
                     module,
                     uid: str,
                     priority: int,
                     time: float = time.time(),
                     status: int | None = None,
                     initial_prompt: str | None = None,
                     whisper_result: str | None = None,
                     whisper_language: str | None = None,
                     whisper_model: str | None = None) -> None:
            """
            Initialisiert einen neuen Moduleintrag und
            verknüpft ihn mit dem Modul.

            :param uid: Die eindeutige ID des Eintrags.
            """
            self.priority: int = priority
            self.time: float = time
            self.module: Default = module
            self.uid: str = uid
            self.status: int | None = status
            self.initial_prompt: str | None = initial_prompt
            self.whisper_result: int | None = whisper_result
            self.whisper_language: str | None = whisper_language
            self.whisper_model: str | None = whisper_model

        def __lt__(self, other) -> bool:
            return self.time < other.time

        def __gt__(self, other) -> bool:
            return self.time > other.time

        def __eq__(self, other) -> bool:
            return self.uid == other.uid

        @abstractmethod
        def queuing(self, ts_api) -> bool:
            """
            Abstrakte Methode zum queuen des Eintrags.
            Kann von Unterklassen implementiert werden.
            :param ts_api: Die aktuelle TsAPI Instanz.
            """
            self.module.queued_or_active = self.module.queued_or_active + 1
            ts_api.add_to_queue(self.priority, self)
            return True

        @abstractmethod
        def preprocessing(self) -> None:
            """
            Abstrakte Methode zur Vorverarbeitung von Daten.
            Kann von Unterklassen implementiert werden.
            """
            pass
