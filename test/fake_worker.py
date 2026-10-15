"""
Replacements for core.whisper_worker.run used by the tests. They run in a
spawned process, so they have to be importable top-level functions.
"""
import os
import time


def large_result(params, result_queue):
    result_queue.put({"type": "language", "language": "de",
                      "model": "fake"})
    # Much larger than the pipe buffer
    segments = [{"start": i, "end": i + 1, "text": "x" * 50}
                for i in range(20000)]
    result_queue.put({"type": "result", "segments": segments,
                      "vad_segments": {"segments": [{"start": 0, "end": 1}],
                                       "audio_duration": 2}})


def error(params, result_queue):
    result_queue.put({"type": "error", "error": "RuntimeError: broken"})


def crash(params, result_queue):
    os._exit(3)


def hang(params, result_queue):
    time.sleep(120)
