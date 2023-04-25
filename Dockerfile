FROM python:3.10-slim

ARG USER="python"
ARG UID="1000"

RUN apt -y update &&\
    apt install -y ffmpeg git &&\
    useradd -m -u ${UID} -s /bin/bash ${USER}

USER ${USER}

COPY ./requirements.txt ./home/${USER}/requirements.txt
RUN pip install --no-warn-script-location -r /home/${USER}/requirements.txt && \
    rm /home/${USER}/requirements.txt

COPY --chown=${USER}:${USER} ./data /home/${USER}/ts-api/data
COPY --chown=${USER}:${USER} ./src /home/${USER}/ts-api/

ENV PATH=/home/${USER}/.local/bin:$PATH
ENV FLASK_APP /home/${USER}/ts-api/app.py
WORKDIR /home/${USER}/ts-api

CMD ["flask", "run", "--host=0.0.0.0"]