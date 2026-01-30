import logging
import threading
import os
import subprocess
import json
import tempfile
from typing import Tuple, Optional

from packages.Default import Default
from faster_whisper import WhisperModel
from utils.subtitle_splitter import process_segments_with_word_timestamps, trim_long_subtitles
from utils.vad_capture import VADLogCapture


def get_audio_duration(file_path: str) -> float:
    """
    Get the duration of an audio file in seconds using ffprobe.
    
    Args:
        file_path: Path to the audio file
        
    Returns:
        Duration in seconds, or 0.0 if unable to determine
    """
    try:
        command = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            str(file_path)
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        duration = float(data["format"]["duration"])
        return duration
    except Exception as e:
        logging.warning(f"Could not get audio duration: {e}")
        return 0.0


def extract_audio_sample(input_path: str, start_seconds: float, 
                         duration_seconds: float = 15.0) -> Optional[str]:
    """
    Extract a sample of audio from a specific timestamp.
    
    Args:
        input_path: Path to the input audio file
        start_seconds: Start time in seconds
        duration_seconds: Duration of sample to extract
        
    Returns:
        Path to temporary sample file, or None if extraction failed
    """
    try:
        # Create temp file for the sample
        temp_file = tempfile.NamedTemporaryFile(
            suffix=".wav", 
            delete=False,
            prefix=f"lang_sample_{int(start_seconds)}_"
        )
        temp_path = temp_file.name
        temp_file.close()
        
        command = [
            "ffmpeg",
            "-y",  # Overwrite
            "-ss", str(start_seconds),  # Start time
            "-i", str(input_path),
            "-t", str(duration_seconds),  # Duration
            "-vn",  # No video
            "-ar", "16000",  # 16kHz sample rate (Whisper requirement)
            "-ac", "1",  # Mono
            "-c:a", "pcm_s16le",  # PCM format
            temp_path
        ]
        
        result = subprocess.run(
            command, 
            capture_output=True, 
            text=True, 
            check=False
        )
        
        if result.returncode != 0:
            logging.warning(f"Failed to extract sample at {start_seconds}s: {result.stderr}")
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            return None
            
        return temp_path
        
    except Exception as e:
        logging.warning(f"Error extracting audio sample: {e}")
        return None


def detect_language_multipoint(model: WhisperModel, file_path: str, 
                                sample_points: list = None) -> Tuple[str, float]:
    """
    Detect language by sampling multiple points in the audio.
    
    Samples at 20%, 40%, 60%, 80% of the audio and returns
    the language with the highest detection confidence.
    
    Args:
        model: WhisperModel instance
        file_path: Path to the audio file
        sample_points: Optional list of percentages (0.0-1.0) to sample at
        
    Returns:
        Tuple of (language_code, probability)
    """
    if sample_points is None:
        sample_points = [0.2, 0.4, 0.6, 0.8]  # 20%, 40%, 60%, 80%
    
    # Get audio duration
    duration = get_audio_duration(file_path)
    
    if duration <= 0:
        logging.warning("Could not determine audio duration, falling back to single-point detection")
        # Fall back to detecting from start
        try:
            segments_gen, info = model.transcribe(
                file_path,
                beam_size=1,
                best_of=1,
                vad_filter=True
            )
            next(segments_gen, None)
            return info.language, info.language_probability
        except Exception as e:
            logging.error(f"Fallback detection failed: {e}")
            return "en", 0.0
    
    logging.info(f"Audio duration: {duration:.1f}s, sampling at {len(sample_points)} points")
    
    detections = []
    sample_files = []  # Track temp files for cleanup
    
    for point in sample_points:
        start_time = duration * point
        
        # Skip if we're too close to the end
        if start_time + 10 > duration:
            continue
            
        logging.debug(f"Sampling language at {start_time:.1f}s ({point*100:.0f}% of audio)")
        
        # Extract sample
        sample_path = extract_audio_sample(file_path, start_time, duration_seconds=15.0)
        
        if sample_path is None:
            continue
            
        sample_files.append(sample_path)
        
        try:
            # Detect language on sample with VAD to skip silence
            segments_gen, info = model.transcribe(
                sample_path,
                beam_size=1,
                best_of=1,
                vad_filter=True,
                vad_parameters={
                    "threshold": 0.5,
                    "min_speech_duration_ms": 250,
                }
            )
            # Trigger detection by consuming generator
            next(segments_gen, None)
            
            if info.language and info.language_probability > 0:
                detections.append({
                    "point": point,
                    "start_time": start_time,
                    "language": info.language,
                    "probability": info.language_probability
                })
                logging.debug(f"  -> Detected '{info.language}' with probability {info.language_probability:.2f}")
                
        except Exception as e:
            logging.warning(f"Detection at {start_time:.1f}s failed: {e}")
            continue
    
    # Clean up temp files
    for temp_file in sample_files:
        try:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
        except Exception:
            pass
    
    if not detections:
        logging.warning("No successful language detections, defaulting to English")
        return "en", 0.0
    
    # Find the detection with highest probability
    best = max(detections, key=lambda x: x["probability"])
    
    # Log all detections for debugging
    detection_summary = [(d['language'], round(d['probability'], 2), f"{d['point']*100:.0f}%") for d in detections]
    logging.info(f"Language detections: {detection_summary}")
    logging.info(f"Best detection: '{best['language']}' with probability {best['probability']:.2f} at {best['point']*100:.0f}%")
    
    return best["language"], best["probability"]


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
            
            # Get configuration
            model_size = os.environ.get("whisper_model")
            device = os.environ.get("whisper_device", "cuda")
            compute_type = os.environ.get("whisper_compute_type", "float16")
            cpu_threads = int(os.environ.get("whisper_cpu_threads", "4"))
            use_vad = os.environ.get("whisper_use_vad", "true").lower() == "true"
            
            # Load Whisper model (faster-whisper)
            model_kwargs = {
                "device": device,
                "compute_type": compute_type,
                "download_root": "./data/models"
            }
            if device == "cpu":
                model_kwargs["cpu_threads"] = cpu_threads
            
            model = WhisperModel(model_size, **model_kwargs)
            
            self.ts_api.database.change_job_entry(self.module_entry.uid,
                                                  "whisper_model",
                                                  model_size)
            
            # Detect language using multi-point sampling for robustness
            # Samples at 20%, 40%, 60%, 80% of audio - better than Whisper's default (start only)
            logging.info(f"Detecting language for job {self.module_entry.uid}...")
            self.whisper_language, detected_prob = detect_language_multipoint(
                model, 
                self.file_path,
                sample_points=[0.2, 0.4, 0.6, 0.8]
            )
            logging.info(f"Detected language: {self.whisper_language} (probability: {detected_prob:.2f})")
            
            self.ts_api.database.change_job_entry(self.module_entry.uid,
                                                  "whisper_language",
                                                  self.whisper_language)
            self.ts_api.database.change_job_entry(self.module_entry.uid,
                                                  "status",
                                                  2)  # processed

            logging.info("Finished processing for job with id "
                         + self.module_entry.uid + "!")

            logging.info("Starting Whisper transcription for job with id "
                         + self.module_entry.uid + "...")
            
            # Prepare transcription parameters
            transcribe_kwargs = {
                "vad_filter": use_vad,
                "word_timestamps": True,  # Enable word-level timestamps for better subtitle splitting
                "no_speech_threshold": 0.4,         # More aggressive about trying to transcribe
                "log_prob_threshold": -1.5,         # Accept lower confidence outputs
            }
            
            # Use the language from our multi-point detection
            transcribe_kwargs["language"] = self.whisper_language
            
            if use_vad:
                # Add VAD parameters for better speech detection
                transcribe_kwargs.update({
                    "vad_parameters": {
                        "threshold": 0.5,
                        "min_speech_duration_ms": 250,
                        "max_speech_duration_s": 15,    # might be important in order to disallow idiotically long subtitle lines
                        "min_silence_duration_ms": 100,
                        "speech_pad_ms": 30,
                    }
                })
                logging.info("VAD enabled for transcription")
            
            if (hasattr(self.module_entry, "initial_prompt")
                    and self.module_entry.initial_prompt):
                transcribe_kwargs["initial_prompt"] = self.module_entry.initial_prompt

            # Set up VAD capture to intercept faster-whisper's debug logs
            vad_capture = VADLogCapture()
            vad_capture.setLevel(logging.DEBUG)
            faster_whisper_logger = logging.getLogger("faster_whisper")
            faster_whisper_logger.addHandler(vad_capture)
            
            try:
                # Transcribe audio with word timestamps
                segments_generator, info = model.transcribe(
                    self.file_path,
                    **transcribe_kwargs
                )
                
                # Convert generator to list with word data for intelligent splitting
                segments_with_words = []
                for segment in segments_generator:
                    # Extract word-level timing if available
                    words = []
                    if segment.words:
                        for word in segment.words:
                            words.append({
                                "word": word.word,
                                "start": word.start,
                                "end": word.end
                            })
                    
                    segments_with_words.append({
                        "start": segment.start,
                        "end": segment.end,
                        "text": segment.text,
                        "words": words
                    })
                
                logging.info(f"Transcription completed: {len(segments_with_words)} segments, "
                            f"duration: {info.duration:.2f}s")
                
                # Apply intelligent subtitle splitting (max 80 chars per line)
                max_line_length = int(os.environ.get("subtitle_max_length", 80))
                segments_list = process_segments_with_word_timestamps(
                    segments_with_words, 
                    max_line_length=max_line_length
                )
                
                logging.info(f"After subtitle splitting: {len(segments_list)} subtitle lines "
                            f"(max {max_line_length} chars per line)")
                
                # Trim any subtitles that are too long (>30s → 20s)
                segments_list = trim_long_subtitles(segments_list, max_duration=30.0, trim_to=20.0)
                
            finally:
                # Remove VAD capture handler
                faster_whisper_logger.removeHandler(vad_capture)
            
            # Save VAD data if captured
            if vad_capture.vad_segments:
                vad_data = {
                    "segments": vad_capture.vad_segments,
                    "audio_duration": vad_capture.audio_duration or info.duration,
                    "vad_removed": vad_capture.vad_removed_duration,
                    "segment_count": len(vad_capture.vad_segments)
                }
                self.ts_api.database.change_job_entry(self.module_entry.uid,
                                                      "vad_segments", vad_data)
                logging.info(f"Captured {len(vad_capture.vad_segments)} VAD segments")
            
            # Store results
            self.whisper_result = segments_list
            self.ts_api.database.change_job_entry(self.module_entry.uid,
                                                  "whisper_result", segments_list)
            self.ts_api.database.change_job_entry(self.module_entry.uid,
                                                  "status",
                                                  3)  # Whispered
            
            # Clean up audio file
            if os.path.exists(self.file_path):
                os.remove(self.file_path)
                logging.debug(f"Removed audio file for job {self.module_entry.uid}")
            
            logging.info(f"Finished Whisper for job with id {self.module_entry.uid}!")
            self.ts_api.unregister_job(self.module_entry)
            
        except Exception as e:
            logging.error(f"Error transcribing job {self.module_entry.uid}: {e}")
            self.ts_api.database.change_job_entry(self.module_entry.uid,
                                                  "status", 4)  # Failed
            self.ts_api.unregister_job(self.module_entry)
