import json
import logging

from faster_whisper.utils import format_timestamp as fw_format_timestamp

from utils import formatters
from utils.subtitle_splitter import (process_segments_with_word_timestamps,
                                     trim_long_subtitles)
from utils.vad_capture import (VADLogCapture, generate_timeline_csv,
                               generate_vad_summary)


SEGMENTS = [{"start": 0.3, "end": 2.5, "text": " Hallo Welt. "},
            {"start": 3661.0, "end": 3662.25, "text": "Zweiter Satz"}]


class TestFormatters:

    def test_srt(self):
        assert formatters.output_srt(SEGMENTS) == (
            "1\n00:00:00,300 --> 00:00:02,500\nHallo Welt.\n\n"
            "2\n01:01:01,000 --> 01:01:02,250\nZweiter Satz\n")

    def test_vtt(self):
        output = formatters.output_vtt(SEGMENTS)
        assert output.startswith("WEBVTT\n")
        assert "00:00:00.300 --> 00:00:02.500\nHallo Welt." in output

    def test_txt_csv_json(self):
        assert formatters.output_txt(SEGMENTS) == "Hallo Welt. Zweiter Satz"
        assert formatters.output_csv(SEGMENTS).splitlines()[1] == \
            "0.300\t2.500\tHallo Welt."
        assert json.loads(formatters.output_json(SEGMENTS))[1]["end"] == \
            3662.25

    def test_rounding(self):
        assert formatters.format_timestamp(0.9999) == "00:00:01,000"
        assert formatters.format_timestamp(59.9996, "vtt") == "00:01:00.000"


class TestSubtitleSplitter:

    def test_long_segment_is_split(self):
        words = [{"word": f" word{i}", "start": i, "end": i + 0.5}
                 for i in range(30)]
        text = "".join(w["word"] for w in words)
        lines = process_segments_with_word_timestamps(
            [{"start": 0, "end": 30, "text": text, "words": words}],
            max_line_length=40)
        assert len(lines) > 1
        assert all(len(line["text"]) <= 40 for line in lines)
        assert " ".join(line["text"] for line in lines) == text.strip()
        assert lines[0]["start"] == 0
        assert lines[-1]["end"] == 29.5

    def test_short_segment_unchanged(self):
        lines = process_segments_with_word_timestamps(
            [{"start": 1, "end": 2, "text": " Kurz ",
              "words": [{"word": " Kurz", "start": 1.1, "end": 1.9}]}])
        assert lines == [{"start": 1.1, "end": 1.9, "text": "Kurz"}]

    def test_trim(self):
        trimmed = trim_long_subtitles([{"start": 0, "end": 40, "text": "x"}])
        assert trimmed[0]["end"] == 20


class TestVadCapture:

    def capture(self, *messages):
        handler = VADLogCapture()
        logger = logging.getLogger("test_vad_capture")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        try:
            for message, *args in messages:
                logger.debug(message, *args)
        finally:
            logger.removeHandler(handler)
        return handler

    def test_messages_in_faster_whisper_format(self):
        # Built like in faster_whisper/transcribe.py
        for duration, removed in ((312.3, 100.5), (5380.69, 3671.434)):
            handler = self.capture(
                ("Processing audio with duration %s",
                 fw_format_timestamp(duration)),
                ("VAD filter removed %s of audio",
                 fw_format_timestamp(removed)),
                ("VAD filter kept the following audio segments: %s",
                 ", ".join("[%s -> %s]" % (fw_format_timestamp(start),
                                           fw_format_timestamp(end))
                           for start, end in ((1.5, 2.25), (3700, 3710.5)))))
            assert handler.audio_duration == duration
            assert handler.vad_removed_duration == removed
            assert handler.vad_segments == [
                {"start": 1.5, "end": 2.25, "duration": 0.75},
                {"start": 3700, "end": 3710.5, "duration": 10.5}]

    def test_timeline(self):
        segments = [{"start": 1.0, "end": 2.0}, {"start": 3.0, "end": 4.0}]
        lines = generate_timeline_csv(segments, 5.0).splitlines()
        assert [line.split(",")[3] for line in lines[1:]] == \
            ["silence", "voice", "silence", "voice", "silence"]
        summary = generate_vad_summary(segments, 5.0)
        assert summary["speech_percentage"] == 40.0
