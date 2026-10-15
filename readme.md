# Transcription API
This program provides a REST API to asynchronously subtitle video and audio files via OpenAI Whisper.

[![Build](https://github.com/uni-halle/ts-api/actions/workflows/build.yml/badge.svg)](https://github.com/uni-halle/ts-api/actions/workflows/build.yml)
[![Test](https://github.com/uni-halle/ts-api/actions/workflows/test.yml/badge.svg)](https://github.com/uni-halle/ts-api/actions/workflows/test.yml)
[![Lint](https://github.com/uni-halle/ts-api/actions/workflows/lint.yml/badge.svg)](https://github.com/uni-halle/ts-api/actions/workflows/lint.yml)


> **Upgrading from a version before the SQLite job database?** Existing jobs and transcripts are not taken over, see [UPGRADING.md](UPGRADING.md).

## Quickstart
Download the repository and create a file `.env` next to `docker-compose.yaml` with the credentials for the API (there are no default credentials, TsAPI does not start without them) and the hosts files may be downloaded from:

    login_username=choose-a-user
    login_password=choose-a-long-password
    allowed_download_hosts=opencast.example.org

Then build and start the container with `docker compose up --build`. The API runs in [gunicorn](https://gunicorn.org/) with a single worker process (the job queue lives in that process), further gunicorn options can be passed in `GUNICORN_CMD_ARGS`.

### Access TsAPI
After the container is started, the API is available under port 5000. Http requests can be sent there (see endpoints documentation for more info).

### Transcribing files
To subtitle a file send a *POST* request to `/transcribe` with the file and the priority (the smaller the higher) in the form-data. You get back a JSON which contains the ID under which the job runs in TsAPI.

### Checking transcription status
After a job has been created, you can query the status of the job via a *GET* request to `/status`. The ID is transferred as a *GET* parameter. Possible states are:
- "Queued" - The job waits for its file to be downloaded/prepared.
- "Prepared" - The file is available, the job waits for a free Whisper worker.
- "Processed" - The job is currently being transcribed.
- "Whispered" - The job is processed and the transcript can be retrieved.
- "Failed" - The job could not be processed because an error occurred with Whisper.
- "Canceled" - The file could not be downloaded or the job was canceled.

For failed and canceled jobs the response contains an `error` field with the reason.

### Request the transcript

After the job has reached the "Whispered" status, the transcript can be requested via *GET* request to `/transcribe`. The ID and the desired format are passed as *GET* parameters.
Possible formats are:
- txt
- vtt
- srt
- csv / tsv (tab separated)
- json

## Configuration

### Environment variables
There are a few environment variables that affect the behavior of TsAPI.

 - "login_username", "login_password" - Credentials for HTTP basic authentication. Required, there are no defaults.
 - "allowed_download_hosts" - Comma separated list of hosts files may be downloaded from (Opencast links), e.g. `opencast.example.org`. An entry starting with a dot also allows all subdomains (`.example.org`), `*` allows every host. Only http and https URLs are accepted, redirects are checked as well. If the variable is not set, every host is allowed and a warning is logged.
 - "whisper_model" - Specifies the [faster-whisper](https://github.com/SYSTRAN/faster-whisper) model to be used (e.g. `large-v3-turbo`, `large-v3`, `medium`, `small`) or the path to a converted model. If the model is not already downloaded, it is downloaded on start (requires internet connection).
 - "whisper_device" - `auto` (default), `cpu` or `cuda`.
 - "whisper_compute_type" - e.g. `int8` (recommended on CPU), `float16` (recommended on GPU) or `default`.
 - "whisper_cpu_threads" - Number of threads Whisper should use on the CPU.
 - "whisper_use_vad" - Skip silence with voice activity detection (default `true`).
 - "subtitle_max_length" - Maximum number of characters per subtitle (default 80).
 - "parallel_workers" - Specifies the maximum number of Whisper instances that can run in parallel. Multithreading is already supported by Whisper and the value of the variable changes depending on your hardware.
 - "parallel_downloads" - Maximum number of files that are downloaded at the same time (default 3). Downloads run independently of the Whisper workers, a failing download only affects its own job.
 - "max_prepared_jobs" - Maximum number of downloaded files that wait for a Whisper worker (default `parallel_downloads + parallel_workers`).
 - "download_connect_timeout", "download_read_timeout" - Timeouts in seconds for connecting and for receiving data (defaults 10 and 60).
 - "download_timeout" - Maximum duration of one download in seconds (default 3600).
 - "download_retries" - How often a download is retried after connection errors, timeouts or HTTP 429/5xx (default 2).
 - "transcription_timeout" - Maximum duration of one transcription in seconds, 0 for no limit (default 0).

The defaults of the other settings are contained in the `.env` file of the image (`src/.env.example`) and can be overwritten by variables in the environment.

### Using it with GPU
faster-whisper supports Nvidia GPUs via CUDA 12 and cuDNN 9. Please use the `cuda_gpu` branch, its image contains the required libraries. Additionally, a local container-toolkit/nvidia driver installation is required.

## Local installation
It is easily possible to run TsAPI locally without Docker (e.g. for development or testing). This requires Python 3.10, ffmpeg and git to be installed on the system.
First you clone the repo into a folder:

    git clone https://github.com/uni-halle/ts-api.git
    cd ts-api

After that you install the Python requirements:

    pip install -r requirements.txt

And you can start TsAPI from the repository folder (the data is stored in `./data`):

    login_username=user login_password=secret python -m flask --app ./src/app.py run

## Tests
Tests are written with PyTest and can be started via `python -m pytest`. They run in a temporary data directory, replace Whisper by fake workers, never download a model and only access a local HTTP server.

Tests with a real Whisper model are skipped by default. They are enabled with `TSAPI_REAL_MODEL_TESTS=1` and download the model given in `TSAPI_TEST_MODEL` (default `tiny`) once into `TSAPI_TEST_MODEL_DIR` (default `.cache/models`), which requires access to Hugging Face. The test audio is in `test/data/audio`, see the README there for its sources and licenses.

## Endpoints

### /transcribe

##### POST
Sends a file or link for subtitling to TsAPI.

_Form parameter:_

 - priority: The priority (a number, the smaller the higher)
 - file: The file, or
 - module, module_id, link: `opencast`, the ID returned by `/module/opencast` and the link to the file (has to match `allowed_download_hosts`)
 - title: Title of the recording, passed to Whisper as initial prompt (optional)

Authentication is done with HTTP basic authentication.

_Returns:_

    {
      "jobId": "1b0732a9-43f3-42c5-8a41-84043d158910"
    }

Errors: 400 (invalid parameters or link not allowed), 415 (neither file nor link), 429 (queue limit of the Opencast module reached), 507 (not enough storage or RAM, or more than 50 jobs queued).

##### GET
Requests the transcript for a specific JobID.

_Get parameter:_

- id: The job ID
- format: The format to request (See Quickstart - Request the transcript)

_Returns:_

    The file in the requested format.

##### DELETE
Delete the database entry for a specific JobID. A running download or transcription of the job is canceled.

_Delete Parameter:_

- id: The Job ID

_Returns:_

    Code 200, OK

### /vad

##### GET
Requests the speech segments found by the voice activity detection.

_Get parameter:_

- id: The Job ID
- format: `speech` (CSV of the speech segments, default), `timeline` (CSV of speech and silence) or `json` (segments and summary)

### /module/opencast

##### POST
Registers an Opencast installation that sends links instead of files.

_Form parameter:_

- max_queue_length: Maximum number of queued or running jobs of this module

_Returns:_

    {
      "moduleId": "0f1c4e8a-2b8e-4a39-9d7c-3c5b8f0a1e2d"
    }

### /model

##### GET
Requests the Whisper model used for a specific JobID.

_Get parameter:_

- id: The Job ID

_Returns:_

    {
      "jobId": "b3a36e0c-f185-4c72-91bf-a7a36e0c777f",
      "model": "large-v3-turbo"
    }

### /language

##### GET
Requests the language for a specific JobID.

_Get parameter:_

- id: The Job ID

_Returns:_

    {
      "jobId": "b3a36e0c-f185-4c72-91bf-a7a36e0c777f",
      "language": "de"
    }

### /status

##### GET
Requests the current status.

_Get parameter:_

- id: The Job ID

_Returns:_

    {
      "jobId": "b3a36e0c-f185-4c72-91bf-a7a36e0c777f",
      "status": "Whispered"
    }

### /status/system

##### Get
Requests the current status of the TsAPI system.

_Returns:_

    {
      "cpu_cores": 12,
      "cpu_usage": 13.3,
      "parallel_jobs": 2,
      "queue_length": 0,
      "ram_free": 29.0,
      "ram_usage": 71.0,
      "storage_free": 120.5,
      "storage_total": 250.0,
      "storage_usage": 129.5,
      "parallel_downloads": 3,
      "running_downloads": 0,
      "running_jobs": 0,
      "swap_free": 78.7,
      "swap_usage": 21.3
    }
