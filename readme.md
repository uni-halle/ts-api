# Transcription API
This program provides a REST API to asynchronously subtitle video and audio files via OpenAI Whisper.


## Quickstart
Download the repository and build the Docker image via `docker build . -t ts-api:local` and launch the image via Docker compose provided by the repository .

### Access TsAPI
After the container is started, the API is available under port 5000. Http requests can be sent there (see endpoints documentation for more info).

### Transcribing files
To subtitle a file send a *POST* request to `/transcribe` with the file and the priority (the smaller the higher) in the form-data. You get back a JSON which contains the ID under which the job runs in TsAPI.

### Checking transcription status
After a job has been created, you can query the status of the job via a *GET* request to `/status`. The ID is transferred as a *GET* parameter. Possible states are:
 - "Prepared" - The job is prepared but not yet processed.
- "Running" - The job is currently being processed.
- "Whispered - The job is processed and the transcript can be retrieved.
- "Failed" - The job could not be processed because an error occurred with Whisper.

### Request the transcript

After the job has reached the "Whispered" status, the transcript can be requested via *GET* request to `/transcribe`. The ID and the desired format are passed as *GET* parameters.
Possible formats are:
- txt
- vtt
- srt
- tsv
- json

## Configuration

### Environment variables
There are a few environment variables that affect the behavior of TsAPI.

 - "whisper_model" - Specifies which whisper model should be used. If the model is not already downloaded, it will try to download it (requires internet connection).
 - "parallel_workers" - Specifies the maximum number of Whisper instances that can run in parallel. Multithreading is already supported by Whisper and the value of the variable changes depending on your hardware.

The default settings are already contained in an .env file, but can be overwritten by variables in the environment.

### Using it with GPU
So technically, thanks to PyTorch, it is possible that Whisper runs via Nvidia Cuda and thus becomes faster. Up to now this has not been tested because the hardware does not exist but the implementation is not in the TsAPI but in the Whisper Python library. It is unclear if the Docker container supports passing the GPU to Python or if it needs to be additionally modified for this.

## Local installation
It is easily possible to run TsAPI locally without Docker (e.g. for development or testing). This requires both Python 3.10, ffmpeg and git to be installed on the system.
First you clone the repo into a folder:

    git clone https://git.itz.uni-halle.de/elearning/opencast/ts-api.git

After that you install the Python requirments:

    pip install -r requirments.txt
And you can start TsAPI with the following command:

    python -m flask --app ./src/app.py run

## Tests
Test are written with PyTest and can be started via `python -m pytest`.
Test coverage covers all functions of the `utils` and the basic creation of `TsAPI` and `Transcriber` objects. Tests do **not** cover the creation of subtitles via Whisper, as this would take too long.

## Endpoints

### /transcribe

##### POST
Sends a file or link for subtitling to TsAPI.

_Form parameter:_
 
 - file: The file
 - link: The link to a file
 - username: The username for auth (optional)
 - password: The password for auth (optional)
 - priority: The priority (> 0)

_Returns:_

    {
      "jobId": "1b0732a9-43f3-42c5-8a41-84043d158910"
    }

##### GET
Requests the transcript for a specific JobID.

_Get parameter:_

- id: The job ID
- format: The format to request (See Quickstart - Request the transcript)

_Returns:_

    The file in the requested format.

##### DELETE
Delete the database entry for a specific JobID.

_Delete Parameter:_

- id: The Job ID

_Returns:_

    Code 200, OK

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
      "running_downloads": 0,
      "running_jobs": 0,
      "swap_free": 78.7,
      "swap_usage": 21.3
    }
