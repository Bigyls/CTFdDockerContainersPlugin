import logging
import logging.handlers
import os
import sys

def init_logs(app):
    logger_containers = logging.getLogger("containers")

    logger_containers.setLevel(logging.INFO)

    log_dir = app.config["LOG_FOLDER"]
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logs = {
        "containers": os.path.join(log_dir, "containers.log"),
    }

    try:
        for log in logs.values():
            if not os.path.exists(log):
                open(log, "a").close()

        containers_log = logging.handlers.RotatingFileHandler(
            logs["containers"], maxBytes=10485760, backupCount=5
        )

        logger_containers.addHandler(containers_log)
    except IOError:
        pass

    stdout = logging.StreamHandler(stream=sys.stdout)

    logger_containers.addHandler(stdout)

    logger_containers.propagate = 0
