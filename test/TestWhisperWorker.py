"""whisper_worker checks that need no model (ffmpeg/ffprobe required)."""
import shutil
import subprocess

import pytest

from core import whisper_worker

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"),
                                reason="ffmpeg missing")


def make(path, *inputs):
    subprocess.run(["ffmpeg", "-v", "error", *inputs, "-t", "1",
                    "-shortest", str(path)], check=True)
    return path


@pytest.fixture
def video_only(tmp_path):
    return make(tmp_path / "video_only.mp4",
                "-f", "lavfi", "-i", "color=c=black:s=64x64:r=5")


@pytest.fixture
def video_with_audio(tmp_path):
    return make(tmp_path / "with_audio.mp4",
                "-f", "lavfi", "-i", "color=c=black:s=64x64:r=5",
                "-f", "lavfi", "-i", "sine=f=440:r=16000")


def test_has_audio_stream(video_only, video_with_audio, tmp_path):
    assert not whisper_worker.has_audio_stream(video_only)
    assert whisper_worker.has_audio_stream(video_with_audio)
    # ffprobe cannot read it: let the decoder report the real error
    broken = tmp_path / "broken.mp4"
    broken.write_bytes(b"not a media file")
    assert whisper_worker.has_audio_stream(broken)


class Queue(list):
    put = list.append


def test_run_reports_a_missing_audio_stream(video_only, monkeypatch):
    def no_model(*args, **kwargs):
        raise AssertionError("the model must not be loaded")
    monkeypatch.setattr(whisper_worker, "WhisperModel", no_model)
    queue = Queue()
    whisper_worker.run({"file_path": str(video_only), "model": "tiny"}, queue)
    assert queue == [{"type": "error", "error": "NoAudioStreamError: the "
                      "media file has no audio stream, nothing to transcribe"}]
