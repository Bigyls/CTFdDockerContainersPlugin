import os
import logging
import logging.handlers
from flask import has_request_context, request
from CTFd.utils.user import get_current_user

class CustomFormatter(logging.Formatter):
    def format(self, record):
        user = get_current_user()
        if has_request_context():
            ip = request.remote_addr
            if ip is not None and ip != "" and ip != "None":
                record.ip = ip
            else:
                record.ip = "Unknown"
        else:
            record.ip = "N/A"

        if '%' in record.msg:
            record.formatted_message = record.msg % record.__dict__
        else:
            record.formatted_message = record.msg.format(**record.__dict__)

        record.loglevel = record.levelname
        record.user_id = user.id if user else 'Unknown'
        return super().format(record)

class LoggerFilter(logging.Filter):
    def __init__(self, logger_name):
        super().__init__()
        self.logger_name = logger_name

    def filter(self, record):
        return record.name == self.logger_name

class LoggingManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LoggingManager, cls).__new__(cls)
            cls._instance.loggers = {}
        return cls._instance

    def init_logs(self, app, log_levels=None):
        if log_levels is None:
            log_levels = {
                "containers_actions": logging.INFO,
                "containers_errors": logging.ERROR,
                "containers_debug": logging.DEBUG,
            }

        log_dir = app.config.get("LOG_FOLDER", "logs")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        log_file = os.path.join(log_dir, "containers.log")

        formatter = CustomFormatter('%(asctime)s|%(loglevel)s|IP:%(ip)s|USER_ID:%(user_id)s|%(formatted_message)s')

        for logger_name, level in log_levels.items():
            logger = logging.getLogger(logger_name)
            logger.setLevel(level)

            handler = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=10485760, backupCount=5
            )
            handler.setFormatter(formatter)
            handler.addFilter(LoggerFilter(logger_name))

            logger.addHandler(handler)
            logger.propagate = False

            self.loggers[logger_name] = logger

    def log(self, logger_name, format, **kwargs):
        logger = self.loggers.get(logger_name)
        if logger is None:
            raise ValueError(f"Unknown logger: {logger_name}")

        if "errors" in logger_name:
            log_method = logger.error
        elif "debug" in logger_name:
            log_method = logger.debug
        else:
            log_method = logger.info

        log_method(format, extra=kwargs)

logging_manager = LoggingManager()

def init_logs(app):
    logging_manager.init_logs(app)

def log(logger_name, format, **kwargs):
    logging_manager.log(logger_name, format, **kwargs)
