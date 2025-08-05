import logging
import threading
import os


from packages.Default import Default
from pywhispercpp.model import Model


class Transcriber:
    def __init__(self, ts_api, module_entry: Default.Entry):
        """
        Creates a Transcriber object to work on subtitles
        :param ts_api: The main ts_api object to call back
        :param module_entry: The module_entry of the job to create the
        transcriber object for
        """
        self.whisper_result = None
        self.whisper_language = None
        self.file_path: str = "./data/audioInput/" + module_entry.uid
        self.ts_api = ts_api
        self.module_entry: Default.Entry = module_entry

    def start_thread(self):
        """
        Starts the thread that whispers the audio
        :return: Nothing
        """
        whisper_thread = threading.Thread(target=self.transcriber_thread,
                                          daemon=True)
        whisper_thread.start()

    def transcriber_thread(self):
        """
        The thread to whisper an audio
        :return: Nothing
        """
        try:
            logging.info("Starting processing for job with id "
                         + self.module_entry.uid + "...")
            # Whisper model
            model_size = os.environ.get("whisper_model")
            model = Model(model_size, models_dir="./data/models")
            self.ts_api.database.change_job_entry(self.module_entry.uid,
                                                  "whisper_model",
                                                  model_size)
            # Detect language
            most_likely, probs = model.auto_detect_language(
                self.file_path, offset_ms=5000)
            self.whisper_language = most_likely[0]
            self.ts_api.database.change_job_entry(self.module_entry.uid,
                                                  "whisper_language",
                                                  self.whisper_language)
            self.ts_api.database.change_job_entry(self.module_entry.uid,
                                                  "status",
                                                  2)  # processed

            logging.info("Finished processing for job with id "
                         + self.module_entry.uid + "!")

            logging.info("Starting Whisper for job with id "
                         + self.module_entry.uid + "...")
            # params
            kwargs = {
                "language": self.whisper_language
            }
            if (hasattr(self.module_entry, "initial_prompt")
                    and self.module_entry.initial_prompt):
                kwargs["initial_prompt"] = self.module_entry.initial_prompt

            # Translate audio
            result = model.transcribe(self.file_path, **kwargs)
            # Store results
            self.whisper_result = result
            self.ts_api.database.change_job_entry(self.module_entry.uid,
                                                  "whisper_result", result)
            self.ts_api.database.change_job_entry(self.module_entry.uid,
                                                  "status",
                                                  3)  # Whispered
            os.remove(self.file_path)
            logging.debug("Finished Whisper for job with id "
                          + self.module_entry.uid + "!")
            self.ts_api.unregister_job(self.module_entry)
        except Exception as e:
            logging.error(e)
            self.ts_api.database.change_job_entry(self.module_entry.uid,
                                                  "status", 4)  # Failed
            self.ts_api.unregister_job(self.module_entry)
