"""
VAD (Voice Activity Detection) log capture and processing.

Captures VAD segment data from faster-whisper's debug logs
and provides utilities for generating timeline CSVs.
"""
import logging
import re
from typing import List, Dict, Tuple, Optional


class VADLogCapture(logging.Handler):
    """
    Custom logging handler that captures VAD segment data
    from faster-whisper's debug output.
    """
    
    def __init__(self):
        super().__init__()
        self.vad_segments: List[Dict[str, float]] = []
        self.audio_duration: Optional[float] = None
        self.vad_removed_duration: Optional[float] = None
        self._raw_message: Optional[str] = None
    
    def reset(self):
        """Reset captured data for a new transcription."""
        self.vad_segments = []
        self.audio_duration = None
        self.vad_removed_duration = None
        self._raw_message = None
    
    def emit(self, record):
        """Capture relevant log messages."""
        msg = record.getMessage()
        
        # Capture audio duration
        # Example: "Processing audio with duration 01:29:40.690"
        if "Processing audio with duration" in msg:
            duration_match = re.search(r'duration (\d+):(\d+):(\d+\.?\d*)', msg)
            if duration_match:
                hours, minutes, seconds = duration_match.groups()
                self.audio_duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        
        # Capture VAD removed duration
        # Example: "VAD filter removed 29:11.434 of audio"
        if "VAD filter removed" in msg:
            removed_match = re.search(r'removed (\d+):(\d+\.?\d*) of audio', msg)
            if removed_match:
                minutes, seconds = removed_match.groups()
                self.vad_removed_duration = int(minutes) * 60 + float(seconds)
        
        # Capture VAD segments
        # Example: "VAD filter kept the following audio segments: [02:22.082 -> 02:22.814], [02:28.930 -> 02:30.238], ..."
        if "VAD filter kept the following audio segments:" in msg:
            self._raw_message = msg
            self.vad_segments = parse_vad_segments(msg)


def parse_timestamp_to_seconds(timestamp: str) -> float:
    """
    Parse timestamp string to seconds.
    Handles both MM:SS.mmm and HH:MM:SS.mmm formats.
    
    Args:
        timestamp: String like "02:22.082" or "01:29:39.394"
        
    Returns:
        Time in seconds as float
    """
    parts = timestamp.split(':')
    
    if len(parts) == 2:
        # MM:SS.mmm format
        minutes = int(parts[0])
        seconds = float(parts[1])
        return minutes * 60 + seconds
    elif len(parts) == 3:
        # HH:MM:SS.mmm format
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds
    else:
        raise ValueError(f"Invalid timestamp format: {timestamp}")


def parse_vad_segments(log_message: str) -> List[Dict[str, float]]:
    """
    Parse VAD segments from the log message.
    
    Args:
        log_message: The log message containing VAD segments
        
    Returns:
        List of segment dicts with 'start' and 'end' in seconds
    """
    segments = []
    
    # Pattern: [TIMESTAMP -> TIMESTAMP] where TIMESTAMP is MM:SS.mmm or HH:MM:SS.mmm
    # Match the content between [ ] and then parse the timestamps separately
    pattern = r'\[([\d:.]+)\s*->\s*([\d:.]+)\]'
    
    for match in re.finditer(pattern, log_message):
        start_str, end_str = match.groups()
        
        start_seconds = parse_timestamp_to_seconds(start_str)
        end_seconds = parse_timestamp_to_seconds(end_str)
        
        segments.append({
            'start': start_seconds,
            'end': end_seconds,
            'duration': round(end_seconds - start_seconds, 3)
        })
    
    return segments


def format_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS.mmm format for consistency."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def format_timestamp_hms(seconds: float) -> str:
    """Convert seconds to HH:MM:SS.mmm format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def generate_speech_csv(vad_segments: List[Dict[str, float]]) -> str:
    """
    Generate CSV with just the speech segments.
    
    Args:
        vad_segments: List of VAD segment dicts
        
    Returns:
        CSV string with speech segments
    """
    lines = ["start,end,duration,start_seconds,end_seconds"]
    
    for seg in vad_segments:
        start_fmt = format_timestamp(seg['start'])
        end_fmt = format_timestamp(seg['end'])
        duration = seg.get('duration', seg['end'] - seg['start'])
        
        lines.append(f"{start_fmt},{end_fmt},{duration:.3f},{seg['start']:.3f},{seg['end']:.3f}")
    
    return "\n".join(lines)


def generate_timeline_csv(vad_segments: List[Dict[str, float]], 
                          audio_duration: float) -> str:
    """
    Generate CSV with full timeline showing voice and silence intervals.
    
    Args:
        vad_segments: List of VAD segment dicts (speech segments)
        audio_duration: Total duration of the audio in seconds
        
    Returns:
        CSV string with full timeline
    """
    if not vad_segments:
        # No speech detected - entire audio is silence
        return "start,end,duration,type,start_seconds,end_seconds\n" + \
               f"00:00:00.000,{format_timestamp(audio_duration)},{audio_duration:.3f},silence,0.000,{audio_duration:.3f}"
    
    lines = ["start,end,duration,type,start_seconds,end_seconds"]
    
    # Sort segments by start time
    sorted_segments = sorted(vad_segments, key=lambda x: x['start'])
    
    current_time = 0.0
    
    for seg in sorted_segments:
        # Add silence before this speech segment (if any)
        if seg['start'] > current_time + 0.001:  # Small tolerance
            silence_duration = seg['start'] - current_time
            lines.append(
                f"{format_timestamp(current_time)},{format_timestamp(seg['start'])},"
                f"{silence_duration:.3f},silence,{current_time:.3f},{seg['start']:.3f}"
            )
        
        # Add speech segment
        speech_duration = seg['end'] - seg['start']
        lines.append(
            f"{format_timestamp(seg['start'])},{format_timestamp(seg['end'])},"
            f"{speech_duration:.3f},voice,{seg['start']:.3f},{seg['end']:.3f}"
        )
        
        current_time = seg['end']
    
    # Add final silence (if any)
    if current_time < audio_duration - 0.001:
        silence_duration = audio_duration - current_time
        lines.append(
            f"{format_timestamp(current_time)},{format_timestamp(audio_duration)},"
            f"{silence_duration:.3f},silence,{current_time:.3f},{audio_duration:.3f}"
        )
    
    return "\n".join(lines)


def generate_vad_summary(vad_segments: List[Dict[str, float]], 
                         audio_duration: float,
                         vad_removed: Optional[float] = None) -> Dict:
    """
    Generate a summary of VAD results.
    
    Args:
        vad_segments: List of VAD segment dicts
        audio_duration: Total duration of audio in seconds
        vad_removed: Duration removed by VAD (if known)
        
    Returns:
        Dict with summary statistics
    """
    if not vad_segments:
        return {
            "audio_duration": audio_duration,
            "speech_duration": 0,
            "silence_duration": audio_duration,
            "speech_percentage": 0,
            "segment_count": 0,
        }
    
    speech_duration = sum(seg['end'] - seg['start'] for seg in vad_segments)
    silence_duration = audio_duration - speech_duration
    
    return {
        "audio_duration": round(audio_duration, 3),
        "audio_duration_formatted": format_timestamp_hms(audio_duration),
        "speech_duration": round(speech_duration, 3),
        "speech_duration_formatted": format_timestamp_hms(speech_duration),
        "silence_duration": round(silence_duration, 3),
        "silence_duration_formatted": format_timestamp_hms(silence_duration),
        "speech_percentage": round(speech_duration / audio_duration * 100, 1),
        "segment_count": len(vad_segments),
        "vad_removed_reported": round(vad_removed, 3) if vad_removed else None,
    }
