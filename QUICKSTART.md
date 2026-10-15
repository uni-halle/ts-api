# Quick Start Guide

## Build & Run

```bash
# Build and start the container
sudo docker compose build
sudo docker compose up

# Full reset (removing volumes)
sudo docker compose down -v
sudo docker compose build 
sudo docker compose up
```

---

## Transcription Workflow

### 1. Submit a job

```bash
# Upload audio file for transcription
curl -X POST \
  -F "file=@audio.mp3" \
  -F "priority=1" \
  -u username:password \
  "http://localhost:5000/transcribe"
```

Returns: `{"id": "abc123-def456-..."}`

### 2. Check job status

```bash
curl -u username:password \
  "http://localhost:5000/transcribe?id=YOUR_JOB_ID"
```

Status codes:
- `0` = Queued
- `1` = Prepared
- `2` = Processing
- `3` = Done
- `4` = Failed

### 3. Get results

```bash
# Get SRT subtitles
curl -u username:password \
  "http://localhost:5000/transcribe?id=YOUR_JOB_ID&format=srt" \
  -o output.srt

# Get VTT subtitles
curl -u username:password \
  "http://localhost:5000/transcribe?id=YOUR_JOB_ID&format=vtt" \
  -o output.vtt

# Get plain text
curl -u username:password \
  "http://localhost:5000/transcribe?id=YOUR_JOB_ID&format=txt" \
  -o output.txt

# Get CSV (tab-separated)
curl -u username:password \
  "http://localhost:5000/transcribe?id=YOUR_JOB_ID&format=csv" \
  -o output.csv
```

### 4. Get VAD (Voice Activity Detection) data

```bash
# Speech segments only (CSV)
curl -u username:password \
  "http://localhost:5000/vad?id=YOUR_JOB_ID&format=speech" \
  -o vad_speech.csv

# Full timeline with voice/silence (CSV)
curl -u username:password \
  "http://localhost:5000/vad?id=YOUR_JOB_ID&format=timeline" \
  -o vad_timeline.csv

# JSON with summary stats
curl -u username:password \
  "http://localhost:5000/vad?id=YOUR_JOB_ID&format=json"
```

### 5. Delete a job

```bash
curl -X DELETE -u username:password \
  "http://localhost:5000/transcribe?id=YOUR_JOB_ID"
```

---

## Configuration Switching

All configuration is in two files. Comment/uncomment blocks as needed.

### Toggle VAD (Voice Activity Detection)

**File:** `docker-compose.yaml`

```yaml
# VAD ON (filters silence)
- whisper_use_vad=true

# VAD OFF (transcribe everything)
- whisper_use_vad=false
```

No rebuild needed — just restart: `sudo docker compose down && sudo docker compose up`

---

### Toggle CPU / GPU Mode

**Two files need changes:**

#### File 1: `Dockerfile`

```dockerfile
# ==============================================================================
# PRODUCTION (GPU) - uncomment for production
# ==============================================================================
# FROM nvidia/cuda:12.3.2-cudnn9-runtime-ubuntu22.04
# RUN apt-get update && \
#     apt-get install -y python3.10 python3-pip ffmpeg git && \
#     ln -s /usr/bin/python3.10 /usr/bin/python && \
#     useradd -m -u 5000 -s /bin/bash python && \
#     rm -rf /var/lib/apt/lists/*

# ==============================================================================
# LOCAL TESTING (CPU) - uncomment for local testing
# ==============================================================================
FROM python:3.10-slim
RUN apt-get update && \
    apt-get install -y ffmpeg git && \
    useradd -m -u 5000 -s /bin/bash python && \
    rm -rf /var/lib/apt/lists/*
```

#### File 2: `docker-compose.yaml`

```yaml
environment:
  # ============================================================
  # PRODUCTION (GPU) - uncomment for production
  # ============================================================
  # - whisper_model=large-v3-turbo
  # - whisper_device=cuda
  # - whisper_compute_type=float16
  
  # ============================================================
  # LOCAL TESTING (CPU) - uncomment for local testing
  # ============================================================
  - whisper_model=tiny
  - whisper_device=cpu
  - whisper_compute_type=int8

# ...

# ============================================================
# GPU reservation - comment out for CPU-only local testing
# ============================================================
# deploy:
#   resources:
#     reservations:
#       devices:
#         - driver: nvidia
#           count: 1
#           capabilities: [gpu]
```

**After switching:** Rebuild required!

```bash
sudo docker compose down
sudo docker compose build
sudo docker compose up
```
