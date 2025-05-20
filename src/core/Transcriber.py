import logging
import threading
import os

import torch

from packages.Default import Default
import whisper


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
            model = whisper.load_model(model_size,
                                       download_root="./data/models")
            self.ts_api.database.change_job_entry(self.module_entry.uid,
                                                  "whisper_model",
                                                  model_size)
            # Load audio
            audio = whisper.load_audio(self.file_path)
            short_audio = whisper.pad_or_trim(audio)
            # Detect language
            mel = (whisper.log_mel_spectrogram(short_audio, model.dims.n_mels)
                   .to(model.device).to(torch.float32))
            _, probs = model.detect_language(mel)
            self.whisper_language = str(max(probs, key=probs.get))
            self.ts_api.database.change_job_entry(self.module_entry.uid,
                                                  "whisper_language",
                                                  str(max(probs,
                                                          key=probs.get)))
            self.ts_api.database.change_job_entry(self.module_entry.uid,
                                                  "status",
                                                  2)  # processed

            logging.info("Finished processing for job with id "
                         + self.module_entry.uid + "!")

            logging.info("Starting Whisper for job with id "
                         + self.module_entry.uid + "...")
            # Initial Prompt
            if hasattr(self.module_entry, "initial_prompt"):
                initial_prompt = self.module_entry.initial_prompt
            else:
                initial_prompt = None
            # Translate audio
            result = whisper.transcribe(model=model,
                                        audio=audio,
                                        initial_prompt=initial_prompt,
                                        language=self.whisper_language,
                                        fp16=False)
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
