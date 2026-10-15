"""
Subtitle line splitting with word-level timestamps.

Splits long subtitle segments into shorter, readable lines
while maintaining accurate timing using word-level timestamps.
"""
from typing import List, Dict, Tuple, Optional


def find_split_point(text: str, max_length: int = 80, search_range: int = 40) -> Optional[int]:
    """
    Find the best point to split a subtitle line.
    
    Prioritizes splitting at punctuation, then at spaces.
    Uses balancing logic to avoid very short remainder lines.
    
    Args:
        text: The text to split
        max_length: Maximum length before splitting (default 80)
        search_range: Range to search backwards for punctuation (default 40)
        
    Returns:
        Index where to split, or None if no split needed
    """
    if len(text) <= max_length:
        return None
    
    # Search backwards from max_length for punctuation
    search_start = max(0, max_length - search_range)
    search_text = text[search_start:max_length]
    
    # Look for punctuation marks - search from right to left
    for i in range(len(search_text) - 1, -1, -1):
        if search_text[i] in '.,:;!?':
            return search_start + i + 1  # Split after the punctuation
    
    # If no punctuation found, look for spaces with balancing logic
    remainder_length = len(text) - max_length
    
    # Find all spaces in the search range
    spaces = []
    for i in range(len(search_text) - 1, -1, -1):
        if search_text[i] == ' ':
            spaces.append(search_start + i + 1)
    
    if spaces:
        # If remainder is long (>70% of max), split closer to max for balance
        if remainder_length > max_length * 0.7:
            return spaces[0]  # First space found (closest to max_length)
        else:
            # Otherwise, split farther to avoid very short remainder
            return spaces[-1]  # Last space found (farthest from max_length)
    
    # If no good split point found, split at max_length
    return max_length


def split_subtitle_line(text: str, words: List[Dict], 
                        segment_start: float, max_length: int = 80) -> List[Tuple[float, float, str]]:
    """
    Split a long subtitle line into multiple shorter lines using word-level timing.
    
    Args:
        text: The text to split
        words: List of word dicts with 'word', 'start', 'end' keys
        segment_start: Start time of the segment (fallback)
        max_length: Maximum characters per subtitle line
        
    Returns:
        List of tuples (start_time, end_time, text) for each line
    """
    text = text.strip()
    
    # No splitting needed for short text
    if len(text) <= max_length:
        if words:
            return [(words[0]['start'], words[-1]['end'], text)]
        else:
            return [(segment_start, segment_start + 1.0, text)]
    
    lines = []
    remaining_text = text
    word_index = 0
    
    while remaining_text and len(remaining_text) > max_length:
        split_point = find_split_point(remaining_text, max_length)
        if split_point is None:
            break
        
        # Get the text for this line
        line_text = remaining_text[:split_point].strip()
        
        # Count words in this line
        line_words = [w for w in line_text.split() if w.strip()]
        line_word_count = len(line_words)
        
        # Get timing from word-level data
        if word_index < len(words) and word_index + line_word_count <= len(words):
            start_time = words[word_index]['start']
            end_time = words[word_index + line_word_count - 1]['end']
        else:
            # Fallback: estimate timing based on character position
            if words:
                total_duration = words[-1]['end'] - words[0]['start']
                total_chars = len(text)
                chars_processed = len(text) - len(remaining_text)
                chars_in_line = len(line_text)
                
                start_time = words[0]['start'] + (chars_processed / total_chars) * total_duration
                end_time = words[0]['start'] + ((chars_processed + chars_in_line) / total_chars) * total_duration
            else:
                # Basic fallback: ~50ms per character
                line_duration = max(1.0, len(line_text) * 0.05)
                start_time = segment_start + (len(lines) * line_duration)
                end_time = start_time + line_duration
        
        lines.append((start_time, end_time, line_text))
        
        # Move to the next part
        remaining_text = remaining_text[split_point:].strip()
        word_index += line_word_count
    
    # Add the remaining text as the last line
    if remaining_text:
        if word_index < len(words):
            start_time = words[word_index]['start']
            end_time = words[-1]['end']
        else:
            # Fallback timing for the last line
            if lines:
                start_time = lines[-1][1]  # Start where previous line ended
                end_time = start_time + max(1.0, len(remaining_text) * 0.05)
            else:
                start_time = segment_start
                end_time = start_time + max(1.0, len(remaining_text) * 0.05)
        
        lines.append((start_time, end_time, remaining_text))
    
    return lines


def process_segments_with_word_timestamps(segments_with_words: List[Dict], 
                                          max_line_length: int = 80) -> List[Dict]:
    """
    Process transcription segments with word timestamps, splitting long lines.
    
    Args:
        segments_with_words: List of segment dicts with 'start', 'end', 'text', 'words'
        max_line_length: Maximum characters per subtitle line
        
    Returns:
        List of processed segment dicts with properly split lines
    """
    processed_segments = []
    
    for segment in segments_with_words:
        text = segment.get('text', '').strip()
        words = segment.get('words', [])
        segment_start = segment.get('start', 0)
        
        if not text:
            continue
        
        # Split the segment if needed
        split_lines = split_subtitle_line(text, words, segment_start, max_line_length)
        
        # Convert back to segment dicts
        for start_time, end_time, line_text in split_lines:
            processed_segments.append({
                'start': start_time,
                'end': end_time,
                'text': line_text
            })
    
    return processed_segments


def trim_long_subtitles(segments: List[Dict], 
                        max_duration: float = 30.0,
                        trim_to: float = 20.0) -> List[Dict]:
    """
    Trim subtitle segments that exceed maximum duration.
    
    Args:
        segments: List of segment dicts with 'start', 'end', 'text'
        max_duration: Maximum allowed duration in seconds (default 30)
        trim_to: Duration to trim to if exceeded (default 20)
        
    Returns:
        List of segments with long durations trimmed
    """
    trimmed_segments = []
    trimmed_count = 0
    
    for segment in segments:
        start = segment.get('start', 0)
        end = segment.get('end', 0)
        duration = end - start
        
        if duration > max_duration:
            # Trim to the specified duration
            new_end = start + trim_to
            trimmed_segments.append({
                'start': start,
                'end': new_end,
                'text': segment.get('text', '')
            })
            trimmed_count += 1
        else:
            trimmed_segments.append(segment)
    
    if trimmed_count > 0:
        import logging
        logging.info(f"Trimmed {trimmed_count} subtitle(s) exceeding {max_duration}s down to {trim_to}s")
    
    return trimmed_segments

