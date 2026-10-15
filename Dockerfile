FROM python:3.10-slim

ARG USER="python"
ARG UID="1000"

# ffmpeg/ffprobe are used to sample the audio for the language detection
RUN apt-get -y update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/* && \
    useradd -m -u ${UID} -s /bin/bash ${USER}

USER ${USER}

COPY ./requirements.txt ./home/${USER}/requirements.txt
RUN pip install --no-warn-script-location -r /home/${USER}/requirements.txt && \
    rm /home/${USER}/requirements.txt

RUN mkdir -p /home/${USER}/ts-api/data/audioInput \
             /home/${USER}/ts-api/data/jobDatabase \
             /home/${USER}/ts-api/data/models \
             /home/${USER}/ts-api/data/moduleDatabase
COPY --chown=${USER}:${USER} ./src /home/${USER}/ts-api/
COPY --chown=${USER}:${USER} ./src/.env.example /home/${USER}/ts-api/.env

ENV PATH=/home/${USER}/.local/bin:$PATH
ENV FLASK_APP=/home/${USER}/ts-api/app.py
WORKDIR /home/${USER}/ts-api

# One worker process: the job queue lives in the process. Further options
# can be passed in GUNICORN_CMD_ARGS.
CMD ["gunicorn", "--workers", "1", "--threads", "8", \
     "--bind", "0.0.0.0:5000", "app:app"]
