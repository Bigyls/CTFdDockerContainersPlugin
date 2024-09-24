import logging
import logging.handlers
import os
import sys

def init_logs(app):
    logger_containers_actions = logging.getLogger("containers_actions")
    logger_containers_errors = logging.getLogger("containers_errors")

    logger_containers_actions.setLevel(logging.INFO)
    logger_containers_errors.setLevel(logging.INFO)

    log_dir = app.config["LOG_FOLDER"]
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logs = {
        "containers_actions": os.path.join(log_dir, "containers_actions.log"),
        "containers_errors": os.path.join(log_dir, "containers_errors.log"),
    }

    try:
        for log in logs.values():
            if not os.path.exists(log):
                open(log, "a").close()

        containers_actions_log = logging.handlers.RotatingFileHandler(
            logs["containers_actions"], maxBytes=10485760, backupCount=5
        )
        containers_errors_log = logging.handlers.RotatingFileHandler(
            logs["containers_errors"], maxBytes=10485760, backupCount=5
        )

        logger_containers_actions.addHandler(containers_actions_log)
        logger_containers_errors.addHandler(containers_errors_log)
    except IOError:
        pass

    stdout = logging.StreamHandler(stream=sys.stdout)

    logger_containers_actions.addHandler(stdout)
    logger_containers_errors.addHandler(stdout)

    logger_containers_actions.propagate = 0
    logger_containers_errors.propagate = 0
