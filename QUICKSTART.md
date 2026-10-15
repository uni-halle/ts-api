# Quick Start Guide

## Build & Run

There are no default credentials. Create a `.env` file next to
`docker-compose.yaml` first (the curl examples below use `username` and
`password`):

```bash
login_username=username
login_password=password
allowed_download_hosts=opencast.example.org
```

```bash
# Build and start the container
docker compose build
docker compose up

# Full reset (removing volumes)
docker compose down -v
docker compose build 
docker compose up
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

Returns: `{"jobId": "abc123-def456-..."}`

### 2. Check job status

```bash
curl -u username:password \
  "http://localhost:5000/status?id=YOUR_JOB_ID"
```

Status values: `Queued`, `Prepared`, `Processed` (transcribing),
`Whispered` (done), `Failed`, `Canceled`.

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

All configuration is in `docker-compose.yaml`.

### Toggle VAD (Voice Activity Detection)

**File:** `docker-compose.yaml`

```yaml
# VAD ON (filters silence)
- whisper_use_vad=true

# VAD OFF (transcribe everything)
- whisper_use_vad=false
```

No rebuild needed — just restart: `docker compose down && docker compose up`

---

### CPU / GPU

`main` builds a CPU image (`whisper_device=cpu`, `whisper_compute_type=int8`).
For Nvidia GPUs use the `cuda_gpu` branch, which uses a CUDA base image and
`whisper_device=cuda`, `whisper_compute_type=float16`.

After switching: rebuild required!

```bash
docker compose down
docker compose build
docker compose up
```
