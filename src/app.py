import logging
import os
import uuid
import tempfile
import psutil

from flask import Flask, request, send_file
from werkzeug.datastructures import FileStorage, Authorization
from pywhispercpp.utils import output_vtt, output_csv, output_srt, output_txt

from packages.File import File
from packages.Opencast import Opencast
from packages.Default import Default
from utils import util
from core.TsApi import TsApi
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

ts_api = TsApi()
ts_api.start_thread()

app.logger.disabled = True
log = logging.getLogger('werkzeug')
log.disabled = True


@app.before_request
def authorisation():
    auth: Authorization = request.authorization
    if not (auth
            and (auth.username == os.environ.get("login_username")
                 and auth.password == os.environ.get("login_password"))):
        return ('Unauthorized', 401, {
            'WWW-Authenticate': 'Basic realm="Login Required"'
        })


# Transcribe Routes
@app.route("/transcribe", methods=['POST'])
def transcribe_post():
    """
    Endpoint to accept videos and links to whisper
    :return: HttpResponse
    """
    uid: str = str(uuid.uuid4())
    priority: str = request.form.get("priority")

    module: str = request.form.get("module")
    module_id: str = request.form.get("module_id")
    link: str = request.form.get("link")
    title: str = request.form.get("title") if "title" in request.form else None

    if ('file' not in request.files) and (not (module and module_id and link)):
        return {"error": "No file or link with module and module id"}, 415

    if not priority or not priority.isnumeric():
        return {"error": "Priority nan"}, 400

    # Self-care system
    ram_usage = round(psutil.virtual_memory().percent, 1)
    cpu_usage = round(psutil.cpu_percent(interval=0.5))
    storage_total = round(psutil.disk_usage('./').total / 1000000000, 1)
    storage_usage = round(psutil.disk_usage('./').used / 1000000000, 1)

    if 100 / storage_total * storage_usage > 90:
        return {"error": "Not enough storage"}, 507

    if ram_usage > 90:
        return {"error": "Not enough ram"}, 507

    if cpu_usage > 400:
        return {"error": "Not enough cpu"}, 507

    if ts_api.database.queue.qsize() > 50:
        return {"error": "The queue is full"}, 507

    # Old File.py upload
    if 'file' in request.files:
        file: FileStorage = request.files['file']
        module_entry: File.Entry = (
            File.Entry(ts_api.file_module,
                       uid,
                       int(priority),
                       initial_prompt=title
                       )
        )
        module_entry.queuing(ts_api, file)
        return {"jobId": uid}, 201
    # Insert modules here
    elif module and module_id:
        if module == "opencast" and link:
            if module_id in ts_api.database.modules:
                module: Default = ts_api.database.modules[module_id]
                module_entry: Opencast.Entry = (
                    Opencast.Entry(module,
                                   uid,
                                   link,
                                   int(priority),
                                   initial_prompt=title
                                   )
                )
                if module_entry.queuing(ts_api):
                    return {"jobId": uid}, 201
                else:
                    return {"error": "Max Opencast Queue length reached"}, 429
            else:
                return {"error": "Module ID not found"}, 400
        else:
            return {"error": "Module not found"}, 400


@app.route("/transcribe", methods=['GET'])
def transcribe_get():
    """
    Endpoint to convert and return captions as given format
    :return: HttpResponse
    """
    req_id = request.args.get("id")
    output_format = request.args.get("format")
    output_formats = ["vtt", "srt", "txt", "csv"]
    if ts_api.database.exists_job(req_id):
        job_data: Default.Entry = ts_api.database.load_job(req_id)
        if job_data.status >= 2:  # Whispered
            if output_format in output_formats:
                writers = {
                    "vtt": output_vtt,
                    "srt": output_srt,
                    "txt": output_txt,
                    "csv": output_csv,
                }
                try:
                    with (tempfile.NamedTemporaryFile(suffix="."
                          + output_format) as
                          tmp):
                        tmp_path = tmp.name
                        writers[output_format](
                            job_data.whisper_result, tmp_path)
                        return send_file(tmp_path, mimetype="text/vtt")
                except Exception as e:
                    logging.debug(e)
                    return {"error": "Error while generating File: "
                                     + str(e)}, 500
            else:
                return {"error": "Output format not supported"}, 200
        else:
            return {"error": "Job not whispered yet"}, 200
    else:
        return {"error": "Job not found"}, 404


@app.route("/transcribe", methods=['DELETE'])
def transcribe_delete():
    """
    Endpoint to delete captions
    :return: HttpResponse
    """
    req_id = request.args.get("id")
    if ts_api.database.exists_job(req_id):
        job_data: Default.Entry = ts_api.database.load_job(req_id)
        if job_data.status <= 1 or job_data.status >= 2:
            ts_api.database.delete_job(req_id)
            return "OK", 200
        else:
            return {"error": "Job currently processing"}, 200
    else:
        return {"error": "Job not found"}, 404


# Add Module Routes here
@app.route("/module/opencast", methods=['POST'])
def module_opencast_post():
    """
    Endpoint to accept videos and links to whisper
    :return: HttpResponse
    """
    max_queue_length: str = request.form.get("max_queue_length")
    if not max_queue_length:
        return {"error": "No max queue length specified"}, 400
    module: Opencast = Opencast(max_queue_length=int(max_queue_length))
    ts_api.database.modules[module.module_uid] = module
    return {"moduleId": module.module_uid}, 201


# Status Routes
@app.route("/status", methods=['GET'])
def status():
    """
    Endpoint to return status of video
    :return: HttpResponse
    """
    req_id = request.args.get("id")
    if ts_api.database.exists_job(req_id):
        job_data: Default.Entry = ts_api.database.load_job(req_id)
        return {"jobId": req_id,
                "status": util.get_status(job_data.status)}, 200
    else:
        return {"error": "Job not found"}, 404


@app.route("/status/system", methods=['GET'])
def system_status():
    """
    Endpoint to return status of system
    :return: HttpResponse
    """
    return {
        "cpu_usage": round(psutil.cpu_percent(interval=0.5)
                           * 100 / psutil.cpu_count(), 1),
        "cpu_cores": psutil.cpu_count(),
        "ram_usage": round(psutil.virtual_memory().percent, 1),
        "ram_free": round(psutil.virtual_memory().available
                          * 100 / psutil.virtual_memory().total, 1),
        "storage_total": round(psutil.disk_usage('./').total / 1000000000, 1),
        "storage_usage": round(psutil.disk_usage('./').used / 1000000000, 1),
        "storage_free": round(psutil.disk_usage('./').free / 1000000000, 1),
        "swap_usage": round(psutil.swap_memory().percent, 1),
        "swap_free": round(psutil.swap_memory().free
                           * 100 / psutil.swap_memory().total, 1),
        "queue_length": ts_api.database.queue.qsize(),
        "running_jobs": len(ts_api.running_jobs),
        "parallel_jobs": int(os.environ.get("parallel_workers"))
    }, 200


@app.route("/", methods=['GET'])
def main():
    """
    Endpoint to return main of system
    :return: HttpResponse
    """
    return {
        "message": "Listening to API calls",
        "status": 200
    }, 200


@app.route("/language", methods=['GET'])
def language_get():
    """
    Endpoint to return language of video
    :return: HttpResponse
    """
    req_id = request.args.get("id")
    if ts_api.database.exists_job(req_id):
        job_data: Default.Entry = ts_api.database.load_job(req_id)
        if hasattr(job_data, "whisper_language"):
            return {"jobId": req_id,
                    "language": job_data.whisper_language}, 200
        else:
            return {"error": "Job not processed"}, 200
    else:
        return {"error": "Job not found"}, 404


@app.route("/model", methods=['GET'])
def model_get():
    """
    Endpoint to return language of video
    :return: HttpResponse
    """
    req_id = request.args.get("id")
    if ts_api.database.exists_job(req_id):
        job_data: Default.Entry = ts_api.database.load_job(req_id)
        if hasattr(job_data, "whisper_model"):  # Whispered
            return {"jobId": req_id,
                    "model": job_data.whisper_model}, 200
        else:
            return {"error": "Job not processed"}, 200
    else:
        return {"error": "Job not found"}, 404
