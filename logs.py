"""
This module provides a custom logging system for the CTFd containers plugin.
It includes a CustomFormatter, LoggerFilter, and LoggingManager to handle
specialized logging requirements.
"""

import os
import logging
import logging.handlers
from flask import has_request_context, request
from CTFd.utils.user import get_current_user

class CustomFormatter(logging.Formatter):
    """
    A custom formatter for log records that includes IP address and user ID.
    """
    def format(self, record):
        """
        Format the specified record.

        Args:
            record (LogRecord): The log record to format.

        Returns:
            str: The formatted log record.
        """
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
    """
    A filter that only allows records from a specific logger.
    """
    def __init__(self, logger_name):
        """
        Initialize the LoggerFilter.

        Args:
            logger_name (str): The name of the logger to allow.
        """
        super().__init__()
        self.logger_name = logger_name

    def filter(self, record):
        """
        Check if the record should be logged.

        Args:
            record (LogRecord): The log record to check.

        Returns:
            bool: True if the record should be logged, False otherwise.
        """
        return record.name == self.logger_name

class LoggingManager:
    """
    A singleton class to manage loggers for the containers plugin.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LoggingManager, cls).__new__(cls)
            cls._instance.loggers = {}
        return cls._instance

    def init_logs(self, app, log_levels=None):
        """
        Initialize loggers for the containers plugin.

        Args:
            app (Flask): The Flask application instance.
            log_levels (dict, optional): A dictionary of logger names and their log levels.
        """
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
        """
        Log a message using the specified logger.

        Args:
            logger_name (str): The name of the logger to use.
            format (str): The message format string.
            **kwargs: Additional keyword arguments to be passed to the logger.

        Raises:
            ValueError: If the specified logger is not found.
        """
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
    """
    Initialize the logging system for the containers plugin.

    Args:
        app (Flask): The Flask application instance.
    """
    logging_manager.init_logs(app)

def log(logger_name, format, **kwargs):
    """
    Log a message using the specified logger.

    Args:
        logger_name (str): The name of the logger to use.
        format (str): The message format string.
        **kwargs: Additional keyword arguments to be passed to the logger.
    """
    logging_manager.log(logger_name, format, **kwargs)
