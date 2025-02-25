import logging
import os

from werkzeug.datastructures import FileStorage

log_level = logging.INFO
if os.getenv("log"):
    log_env = os.getenv("log").lower()
    if log_env == "warn":
        log_level = logging.WARN
    elif log_env == "debug":
        log_level = logging.DEBUG

logging.basicConfig(format='%(asctime)s [%(module)s]'
                           '%(levelname)s: %(message)s',
                    datefmt='%d.%m.%Y %H:%M:%S',
                    level=log_level)


# Filesystem
def save_file(file: FileStorage, uid: str) -> bool:
    """
    Saves a file to the audioInput folder
    :param file: The file to save
    :param uid: The uid of the job the file belongs to
    :return: Nothing
    """
    try:
        file_path = os.path.join(os.getcwd(), "data", "audioInput", uid)
        file.save(file_path)
        return True
    except Exception as e:
        logging.error(e)
        return False




# Helper
def get_status(status_id: int):
    """
    Returns the name of the status corresponding to the number
    :param status_id: The status number
    :return: The corresponding name of status
    """
    status = {
        0: "Queued",
        1: "Prepared",
        2: "Processed",
        3: "Whispered",
        4: "Failed",
        5: "Canceled"
    }
    return status.get(status_id, 'error')
