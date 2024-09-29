"""
This module initializes and sets up the containers plugin for CTFd.

It handles the registration of the container challenge type, sets up logging,
and registers the plugin's routes and assets with the CTFd application.
"""

from flask import Flask
from flask.blueprints import Blueprint

from CTFd.plugins import register_plugin_assets_directory
from CTFd.plugins.challenges import CHALLENGE_CLASSES

from .container_challenge import ContainerChallenge
from .setup import setup_default_configs
from .routes import register_app
from .logs import init_logs

def load(app: Flask) -> None:
    """
    Initialize and set up the containers plugin for CTFd.

    This function is called by CTFd when the plugin is loaded. It performs the following tasks:
    1. Disables Flask-RESTX's automatic 404 help messages.
    2. Creates all necessary database tables.
    3. Runs the default configuration setup if the plugin hasn't been set up before.
    4. Registers the ContainerChallenge class with CTFd's challenge system.
    5. Registers the plugin's static assets directory.
    6. Initializes logging for the plugin.
    7. Registers the plugin's routes with the CTFd application.

    Args:
        app (Flask): The Flask application instance of CTFd.

    Returns:
        None
    """
    app.config['RESTX_ERROR_404_HELP'] = False
    app.db.create_all()
    setup_default_configs()
    CHALLENGE_CLASSES["container"] = ContainerChallenge
    register_plugin_assets_directory(app, base_path="/plugins/containers/assets/")

    # Initialize logging for this plugin
    init_logs(app)

    # Get the blueprint from register_app and register it here
    containers_bp: Blueprint = register_app(app)
    app.register_blueprint(containers_bp)
