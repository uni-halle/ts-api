"""
Output formatters for faster-whisper transcription results.
Converts transcription segments to various subtitle/transcript formats.
"""
import json
from typing import List, Any


def format_timestamp(seconds: float, format_type: str = "srt") -> str:
    """
    Format a timestamp in seconds to SRT or VTT format.
    
    Args:
        seconds: Time in seconds
        format_type: Either "srt" (HH:MM:SS,mmm) or "vtt" (HH:MM:SS.mmm)
    
    Returns:
        Formatted timestamp string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    
    if format_type == "vtt":
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
    else:  # srt
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def output_srt(segments: List[Any]) -> str:
    """
    Convert transcription segments to SRT format.
    
    Args:
        segments: List of transcription segments (faster-whisper Segment objects or dicts)
    
    Returns:
        SRT formatted string
    """
    srt_output = []
    
    for i, segment in enumerate(segments, 1):
        # Handle both Segment objects and dicts
        if hasattr(segment, 'text'):
            text = segment.text.strip()
            start = segment.start
            end = segment.end
        else:
            text = segment.get('text', '').strip()
            start = segment.get('start', 0)
            end = segment.get('end', 0)
        
        start_time = format_timestamp(start, "srt")
        end_time = format_timestamp(end, "srt")
        
        srt_output.append(f"{i}\n{start_time} --> {end_time}\n{text}\n")
    
    return "\n".join(srt_output)


def output_vtt(segments: List[Any]) -> str:
    """
    Convert transcription segments to WebVTT format.
    
    Args:
        segments: List of transcription segments
    
    Returns:
        VTT formatted string
    """
    vtt_output = ["WEBVTT\n"]
    
    for segment in segments:
        # Handle both Segment objects and dicts
        if hasattr(segment, 'text'):
            text = segment.text.strip()
            start = segment.start
            end = segment.end
        else:
            text = segment.get('text', '').strip()
            start = segment.get('start', 0)
            end = segment.get('end', 0)
        
        start_time = format_timestamp(start, "vtt")
        end_time = format_timestamp(end, "vtt")
        
        vtt_output.append(f"{start_time} --> {end_time}\n{text}\n")
    
    return "\n".join(vtt_output)


def output_txt(segments: List[Any]) -> str:
    """
    Convert transcription segments to plain text.
    
    Args:
        segments: List of transcription segments
    
    Returns:
        Plain text string
    """
    text_parts = []
    
    for segment in segments:
        # Handle both Segment objects and dicts
        if hasattr(segment, 'text'):
            text = segment.text.strip()
        else:
            text = segment.get('text', '').strip()
        
        text_parts.append(text)
    
    return " ".join(text_parts)


def output_csv(segments: List[Any]) -> str:
    """
    Convert transcription segments to CSV format (TSV actually).
    
    Args:
        segments: List of transcription segments
    
    Returns:
        TSV formatted string
    """
    csv_output = ["start\tend\ttext"]
    
    for segment in segments:
        # Handle both Segment objects and dicts
        if hasattr(segment, 'text'):
            text = segment.text.strip()
            start = segment.start
            end = segment.end
        else:
            text = segment.get('text', '').strip()
            start = segment.get('start', 0)
            end = segment.get('end', 0)
        
        # Format with millisecond precision
        csv_output.append(f"{start:.3f}\t{end:.3f}\t{text}")
    
    return "\n".join(csv_output)


def output_json(segments: List[Any]) -> str:
    """
    Convert transcription segments to JSON format.
    
    Args:
        segments: List of transcription segments
    
    Returns:
        JSON formatted string
    """
    json_segments = []
    
    for segment in segments:
        # Handle both Segment objects and dicts
        if hasattr(segment, 'text'):
            json_segments.append({
                'start': segment.start,
                'end': segment.end,
                'text': segment.text.strip()
            })
        else:
            json_segments.append({
                'start': segment.get('start', 0),
                'end': segment.get('end', 0),
                'text': segment.get('text', '').strip()
            })
    
    return json.dumps(json_segments, indent=2, ensure_ascii=False)

