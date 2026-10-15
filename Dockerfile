# ==============================================================================
# PRODUCTION (GPU) - uncomment this block for production
# ==============================================================================
# FROM nvidia/cuda:12.3.2-cudnn9-runtime-ubuntu22.04
# RUN apt-get update && \
#     apt-get install -y python3.10 python3-pip ffmpeg git && \
#     ln -s /usr/bin/python3.10 /usr/bin/python && \
#     useradd -m -u 5000 -s /bin/bash python && \
#     rm -rf /var/lib/apt/lists/*

# ==============================================================================
# LOCAL TESTING (CPU) - uncomment this block for local testing
# ==============================================================================
FROM python:3.10-slim
RUN apt-get update && \
    apt-get install -y ffmpeg git && \
    useradd -m -u 5000 -s /bin/bash python && \
    rm -rf /var/lib/apt/lists/*

# ==============================================================================
# Common setup (no changes needed below)
# ==============================================================================
USER python

COPY ./requirements.txt ./home/python/requirements.txt
RUN pip install --no-warn-script-location -r /home/python/requirements.txt && \
    rm /home/python/requirements.txt

RUN mkdir -p /home/python/ts-api/data/audioInput \
             /home/python/ts-api/data/jobDatabase \
             /home/python/ts-api/data/models \
             /home/python/ts-api/data/moduleDatabase
COPY --chown=python:python ./src /home/python/ts-api/
COPY --chown=python:python ./src/.env.example /home/python/ts-api/.env

ENV PATH=/home/python/.local/bin:$PATH
ENV FLASK_APP=/home/python/ts-api/app.py
WORKDIR /home/python/ts-api

CMD ["flask", "run", "--host=0.0.0.0"]