import logging
import os
import uuid
from threading import Thread

import io
import psutil

import whisper.utils
from flask import Flask, request, Response
from werkzeug.datastructures import FileStorage, Authorization

from utils import database, util
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


@app.route("/transcribe", methods=['POST'])
def transcribe_post():
    """
    Endpoint to accept videos and links to whisper
    :return: HttpResponse
    """
    username: str = request.form.get("username")
    password: str = request.form.get("password")
    priority: str = request.form.get("priority")
    link: str = request.form.get("link")
    if ('file' not in request.files) and (not link):
        return {"error": "No file or link"}, 415

    if not priority.isnumeric():
        return {"error": "Priority nan"}, 400

    if 'file' in request.files:
        try:
            file: FileStorage = request.files['file']
            if file.filename == '':
                return {"error": "No file"}, 415
            if file:
                uid = str(uuid.uuid4())
                ts_api.add_file_to_queue(uid, file, int(priority))
                return {"jobId": uid}, 201
        except:
            return {"Error": "Failed to add file"}, 400
    elif link:
        try:
            uid = str(uuid.uuid4())
            Thread(target=ts_api.add_link_to_queue,
                   args=(uid, link, username, password, int(priority))).start()
            return {"jobId": uid}, 201
        except:
            return {"Error": "Failed to add link"}, 400


@app.route("/status", methods=['GET'])
def status():
    """
    Endpoint to return status of video
    :return: HttpResponse
    """
    req_id = request.args.get("id")
    if database.exists_job(req_id):
        job_data = database.load_job(req_id)
        return {"jobId": req_id,
                "status": util.get_status(job_data["status"])}, 200
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
        "queue_length": (ts_api.queue.qsize() + len(ts_api.runningDownloads)),
        "running_jobs": len(ts_api.runningJobs),
        "parallel_jobs": int(os.environ.get("parallel_workers")),
        "running_downloads": len(ts_api.runningDownloads)
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


@app.route("/transcribe", methods=['GET'])
def transcribe_get():
    """
    Endpoint to convert and return captions as given format
    :return: HttpResponse
    """
    req_id = request.args.get("id")
    output_format = request.args.get("format")
    output_formats = ["vtt", "srt", "txt", "json", "tsv"]
    if database.exists_job(req_id):
        job_data = database.load_job(req_id)
        if job_data["status"] >= 2:  # Whispered
            if output_format in output_formats:
                writers = {
                    "txt": whisper.utils.WriteTXT,
                    "vtt": whisper.utils.WriteVTT,
                    "srt": whisper.utils.WriteSRT,
                    "tsv": whisper.utils.WriteTSV,
                    "json": whisper.utils.WriteJSON,
                }
                try:
                    with io.StringIO() as file:
                        writer = writers[output_format]("./data")
                        writer.write_result(
                            job_data['whisper_result'],
                            file,
                            {"max_line_width": 55,
                             "max_line_count": 2,
                             "highlight_words": False}
                        )
                        return Response(file.getvalue(), mimetype="text/vtt")
                except Exception as e:
                    logging.debug(e)
                    return "{}", 500
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
    if database.exists_job(req_id):
        job_data = database.load_job(req_id)
        if job_data["status"] <= 1 or job_data["status"] >= 2:
            database.delete_job(req_id)
            return "OK", 200
        else:
            return {"error": "Job currently processing"}, 200
    else:
        return {"error": "Job not found"}, 404


@app.route("/language", methods=['GET'])
def language_get():
    """
    Endpoint to return language of video
    :return: HttpResponse
    """
    req_id = request.args.get("id")
    if database.exists_job(req_id):
        if database.load_job(req_id)["status"] >= 2:  # Whispered
            job_data = database.load_job(req_id)
            return {"jobId": req_id,
                    "language": job_data["whisper_language"]}, 200
        else:
            return {"error": "Job not whispered"}, 200
    else:
        return {"error": "Job not found"}, 404
