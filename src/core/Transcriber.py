import logging
import threading
import os
from utils import database
import whisper


class Transcriber:
    def __init__(self, ts_api, uid: str):
        """
        Creates a Transcriber object to work on subtitles
        :param ts_api: The main ts_api object to call back
        :param uid: The uid of the job to create the transcriber object for
        """
        logging.debug("Preparing Transcriber for job with id " + uid + "...")
        # Prepare
        job_data = database.load_job(uid)
        self.whisper_result = None
        self.whisper_language = None
        self.file_path = "./data/audioInput/" + uid
        self.uid = uid
        self.ts_api = ts_api
        database.change_job_status(self.uid, 0)  # Prepared
        logging.debug("Prepared Transcriber for job with id " + self.uid + "!")

    def start_thread(self):
        """
        Starts the thread that whispers the audio
        :return: Nothing
        """
        whisper_thread = threading.Thread(target=self.transcriber_thread)
        whisper_thread.start()
        database.change_job_status(self.uid, 1)  # Running

    def transcriber_thread(self):
        """
        The thread to whisper an audio
        :return: Nothing
        """
        try:
            logging.debug("Starting Whisper for job with id "
                          + self.uid + "...")
            # Whisper
            model_size = os.environ.get("whisper_model")
            model = whisper.load_model(model_size,
                                       download_root="./data/models")
            audio = whisper.load_audio(self.file_path)
            result = whisper.transcribe(model, audio)
            self.whisper_result = result
            database.set_whisper_result(self.uid, result)
            self.whisper_language = result['language']
            database.set_whisper_language(self.uid, result['language'])
            database.set_whisper_model(self.uid, model_size)
            database.change_job_status(self.uid, 2)  # Whispered
            os.remove(self.file_path)
            logging.debug("Finished Whisper for job with id " + self.uid + "!")
            self.ts_api.unregister_job(self.uid)
        except Exception as e:
            os.remove(self.file_path)
            logging.error(e)
            database.change_job_status(self.uid, 3)  # Failed
            self.ts_api.unregister_job(self.uid)
