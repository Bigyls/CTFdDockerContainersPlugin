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
        user = get_current_user()  # Get the current user object.
        if has_request_context():
            ip = request.remote_addr  # Get the remote IP address of the request.
            if ip is not None and ip != "" and ip != "None":
                record.ip = ip  # Assign IP address to the log record.
            else:
                record.ip = "Unknown"  # Default value for unknown IP.
        else:
            record.ip = "N/A"  # Set to N/A if not in request context.

        if '%' in record.msg:
            record.formatted_message = record.msg % record.__dict__  # Format message using old-style formatting.
        else:
            record.formatted_message = record.msg.format(**record.__dict__)  # Format message using new-style formatting.

        record.loglevel = record.levelname  # Store the log level in the record.
        record.user_id = user.id if user else 'Unknown'  # Store the user ID in the record.
        return super().format(record)  # Call the parent class's format method.

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
        self.logger_name = logger_name  # Store the logger name.

    def filter(self, record):
        """
        Check if the record should be logged.

        Args:
            record (LogRecord): The log record to check.

        Returns:
            bool: True if the record should be logged, False otherwise.
        """
        return record.name == self.logger_name  # Only allow records that match the logger name.

class LoggingManager:
    """
    A singleton class to manage loggers for the containers plugin.
    """
    _instance = None  # Class-level instance variable for singleton pattern.

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LoggingManager, cls).__new__(cls)  # Create a new instance if none exists.
            cls._instance.loggers = {}  # Initialize an empty dictionary for loggers.
        return cls._instance  # Return the singleton instance.

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
            }  # Default log levels if none are provided.

        log_dir = app.config.get("LOG_FOLDER", "logs")  # Get the log directory from app config.
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)  # Create the log directory if it doesn't exist.

        log_file = os.path.join(log_dir, "containers.log")  # Specify the log file name.

        # Create a formatter for the logs.
        formatter = CustomFormatter('%(asctime)s|%(loglevel)s|IP:%(ip)s|USER_ID:%(user_id)s|%(formatted_message)s')

        for logger_name, level in log_levels.items():
            logger = logging.getLogger(logger_name)  # Get the logger by name.
            logger.setLevel(level)  # Set the logger's level.

            handler = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=10485760, backupCount=5  # Create a rotating file handler for the logs.
            )
            handler.setFormatter(formatter)  # Set the custom formatter for the handler.
            handler.addFilter(LoggerFilter(logger_name))  # Add the filter to the handler.

            logger.addHandler(handler)  # Attach the handler to the logger.
            logger.propagate = False  # Prevent log messages from being propagated to ancestor loggers.

            self.loggers[logger_name] = logger  # Store the logger in the instance dictionary.

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
        logger = self.loggers.get(logger_name)  # Retrieve the logger from the instance.
        if logger is None:
            raise ValueError(f"Unknown logger: {logger_name}")  # Raise error if logger not found.

        # Determine the logging method based on logger name.
        if "errors" in logger_name:
            log_method = logger.error
        elif "debug" in logger_name:
            log_method = logger.debug
        else:
            log_method = logger.info

        log_method(format, extra=kwargs)  # Log the message using the determined method.

logging_manager = LoggingManager()  # Create a singleton instance of LoggingManager.

def init_logs(app):
    """
    Initialize the logging system for the containers plugin.

    Args:
        app (Flask): The Flask application instance.
    """
    logging_manager.init_logs(app)  # Call the init_logs method of the logging manager.

def log(logger_name, format, **kwargs):
    """
    Log a message using the specified logger.

    Args:
        logger_name (str): The name of the logger to use.
        format (str): The message format string.
        **kwargs: Additional keyword arguments to be passed to the logger.
    """
    logging_manager.log(logger_name, format, **kwargs)  # Log the message through the logging manager.
