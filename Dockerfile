# One Dockerfile for CPU and Nvidia GPU images:
#   docker build .                            # CPU (default)
#   docker build --build-arg VARIANT=cuda .   # Nvidia GPU (CUDA 12, cuDNN 9)
# Only the selected base stage is built.
ARG VARIANT=cpu

FROM python:3.10-slim AS base-cpu
ENV TSAPI_UID=1000

# faster-whisper (CTranslate2) needs CUDA 12 and cuDNN 9
FROM nvidia/cuda:12.6.3-cudnn-runtime-ubuntu24.04 AS base-cuda
# UID 1000 belongs to the image's "ubuntu" user
ENV TSAPI_UID=5000 \
    PIP_BREAK_SYSTEM_PACKAGES=1
RUN apt-get -y update && \
    apt-get install -y --no-install-recommends python3 python3-pip && \
    rm -rf /var/lib/apt/lists/*

FROM base-${VARIANT}

ARG USER="python"
# empty = 1000 (cpu) / 5000 (cuda)
ARG UID=""

# ffmpeg/ffprobe are used to sample the audio for the language detection
RUN apt-get -y update && \
    apt-get install -y --no-install-recommends ffmpeg ca-certificates && \
    rm -rf /var/lib/apt/lists/* && \
    useradd -m -u "${UID:-$TSAPI_UID}" -s /bin/bash ${USER}

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

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
# One worker process: the job queue lives in the process. Further options
# can be passed in GUNICORN_CMD_ARGS.
CMD ["gunicorn", "--workers", "1", "--threads", "8", \
     "--bind", "0.0.0.0:5000", "app:app"]
