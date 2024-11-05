import logging
import threading
import os

import torch

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
            # Whisper model
            model_size = os.environ.get("whisper_model")
            model = whisper.load_model(model_size,
                                       download_root="./data/models")
            database.set_whisper_model(self.uid, model_size)
            # Load audio
            audio = whisper.load_audio(self.file_path)
            short_audio = whisper.pad_or_trim(audio)
            # Detect language
            mel = (whisper.log_mel_spectrogram(short_audio, model.dims.n_mels)
                   .to(model.device).to(torch.float32))
            _, probs = model.detect_language(mel)
            self.whisper_language = str(max(probs, key=probs.get))
            database.set_whisper_language(self.uid,
                                          str(max(probs, key=probs.get)))
            database.change_job_status(self.uid, 4)  # Preprocessed
            # Translate audio
            result = whisper.transcribe(model=model,
                                        audio=audio,
                                        language=self.whisper_language,
                                        fp16=False)
            # Store results
            self.whisper_result = result
            database.set_whisper_result(self.uid, result)
            database.change_job_status(self.uid, 2)  # Whispered
            os.remove(self.file_path)
            logging.debug("Finished Whisper for job with id " + self.uid + "!")
            self.ts_api.unregister_job(self.uid)
        except Exception as e:
            os.remove(self.file_path)
            logging.error(e)
            database.change_job_status(self.uid, 3)  # Failed
            self.ts_api.unregister_job(self.uid)
