# Upgrading

## To the SQLite / faster-whisper version

This version replaces the JSON job database by SQLite and whisper.cpp
(pywhispercpp) by faster-whisper.

### Existing jobs and transcripts are lost

The job database moved from JSON files (`data/jobDatabase/*.json`,
`data/moduleDatabase/*.json`, `data/queue.json`) to SQLite
(`data/tsapi.db`). The JSON files are **not imported**:

- jobs that are still queued or running when you upgrade are lost and have
  to be submitted again,
- transcripts of finished jobs can no longer be requested (`Job not found`),
- registered Opencast modules are lost: register them again with
  `POST /module/opencast` and configure the new module IDs in Opencast,
  otherwise new jobs are rejected with `Module ID not found`.

To upgrade without losing work:

1. Stop submitting new jobs.
2. Wait until `GET /status/system` reports `queue_length`, `running_jobs` and
   `running_downloads` as 0.
3. Fetch all transcripts you still need.
4. Upgrade, register the Opencast modules again and update their IDs in
   Opencast.

Afterwards the old JSON files and the whisper.cpp models (`data/models/*.bin`)
can be deleted. faster-whisper downloads its models into `data/models` again.

### Configuration changes

- `login_username` and `login_password` have no defaults any more, TsAPI and
  `docker compose` refuse to start without them. Put them e.g. into a `.env`
  file next to `docker-compose.yaml`.
- Set `allowed_download_hosts` to the hosts of your Opencast installations.
  Without it every host is allowed and a warning is logged.
- Models are faster-whisper models: whisper.cpp model names like
  `large-v3-turbo-q5_0` do not work any more, use e.g. `large-v3-turbo`.
- New variables: `whisper_device`, `whisper_compute_type`, `whisper_use_vad`,
  `subtitle_max_length`, `parallel_downloads` and the download and
  transcription timeouts, see the [readme](readme.md#environment-variables).
- The container runs gunicorn instead of the Flask development server. Keep
  a single worker process (`--workers 1`), the job queue lives in it.
- The `cuda_gpu` image is based on CUDA 12 with cuDNN 9 (required by
  faster-whisper) instead of CUDA 13.

### API changes

- `DELETE /transcribe` cancels running downloads and transcriptions.
- `GET /status` contains an `error` field for failed and canceled jobs.
- New: `GET /vad`, the formats `json` and `tsv`, `running_downloads` and
  `parallel_downloads` in `GET /status/system`.
- `POST /transcribe` no longer rejects jobs because of the CPU load (the check
  never worked), and rejects links to hosts that are not allowed (400).
