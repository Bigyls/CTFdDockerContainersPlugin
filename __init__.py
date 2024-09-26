from flask import Flask

from CTFd.plugins import register_plugin_assets_directory
from CTFd.plugins.challenges import CHALLENGE_CLASSES
from CTFd.utils import get_config

from .container_challenge import ContainerChallenge
from .setup import setup_default_configs
from .routes import register_app
from .logs import init_logs

def load(app: Flask):
    app.config['RESTX_ERROR_404_HELP'] = False
    app.db.create_all()
    if not get_config("containers:setup"):
        setup_default_configs()
    CHALLENGE_CLASSES["container"] = ContainerChallenge
    register_plugin_assets_directory(app, base_path="/plugins/containers/assets/")

    # Initialize logging for this plugin
    init_logs(app)

    # Get the blueprint from register_app and register it here
    containers_bp = register_app(app)
    app.register_blueprint(containers_bp)
