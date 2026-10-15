#!/usr/bin/env python3
"""
Visualize VAD timeline as a horizontal bar chart.
Voice segments in green, silence in gray.
"""
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import sys

def format_time(seconds):
    """Format seconds as HH:MM:SS"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"

def visualize_vad(csv_path, output_path=None):
    # Read CSV
    df = pd.read_csv(csv_path)
    
    # Get total duration
    total_duration = df['end_seconds'].max()
    
    # Calculate stats
    voice_duration = df[df['type'] == 'voice']['duration'].sum()
    silence_duration = df[df['type'] == 'silence']['duration'].sum()
    voice_pct = (voice_duration / total_duration) * 100
    
    # Create figure
    fig, ax = plt.subplots(figsize=(16, 3))
    
    # Plot each segment as a horizontal bar
    for _, row in df.iterrows():
        color = '#2ecc71' if row['type'] == 'voice' else '#ecf0f1'
        ax.barh(
            y=0, 
            width=row['duration'], 
            left=row['start_seconds'],
            height=0.8,
            color=color,
            edgecolor='#bdc3c7' if row['type'] == 'silence' else '#27ae60',
            linewidth=0.5
        )
    
    # Styling
    ax.set_xlim(0, total_duration)
    ax.set_ylim(-0.5, 0.5)
    ax.set_yticks([])
    ax.set_xlabel('Time', fontsize=12)
    ax.set_title(
        f'VAD Timeline - Total: {format_time(total_duration)} | '
        f'Voice: {format_time(voice_duration)} ({voice_pct:.1f}%) | '
        f'Silence: {format_time(silence_duration)} ({100-voice_pct:.1f}%)',
        fontsize=12,
        fontweight='bold'
    )
    
    # Format x-axis with time labels
    max_ticks = 20
    tick_interval = total_duration / max_ticks
    # Round to nice intervals (30s, 1min, 5min, 10min, etc.)
    nice_intervals = [30, 60, 120, 300, 600, 900, 1800, 3600]
    for interval in nice_intervals:
        if tick_interval <= interval:
            tick_interval = interval
            break
    
    ticks = list(range(0, int(total_duration) + 1, int(tick_interval)))
    ax.set_xticks(ticks)
    ax.set_xticklabels([format_time(t) for t in ticks], rotation=45, ha='right')
    
    # Legend
    voice_patch = mpatches.Patch(color='#2ecc71', label='Voice')
    silence_patch = mpatches.Patch(color='#ecf0f1', edgecolor='#bdc3c7', label='Silence')
    ax.legend(handles=[voice_patch, silence_patch], loc='upper right')
    
    # Grid
    ax.grid(axis='x', alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"Saved to {output_path}")
    else:
        plt.show()

if __name__ == "__main__":
    csv_file = sys.argv[1] if len(sys.argv) > 1 else "vad_timeline2.csv"
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    visualize_vad(csv_file, output_file)

