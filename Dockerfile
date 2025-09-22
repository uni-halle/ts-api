FROM nvidia/cuda:13.0.1-cudnn-devel-ubuntu24.04
#FROM python:3.10-slim

ARG USER="python"
ARG UID="5000"

RUN apt-get -y update && \
    apt-get install -y python3 python3-pip ffmpeg git gcc clang clang-tools cmake sudo bash ca-certificates wget curl make linux-headers-$(uname -r) && \
    useradd -m -u ${UID} -s /bin/bash ${USER}

ENV CC=clang
ENV CXX=clang++
ENV GGML_CUDA=1
ENV NO_REPAIR=1

USER ${USER}

COPY ./requirements.txt ./home/${USER}/requirements.txt
RUN pip install --no-warn-script-location --break-system-packages -r /home/${USER}/requirements.txt && \
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
CMD ["flask", "run", "--host=0.0.0.0"]