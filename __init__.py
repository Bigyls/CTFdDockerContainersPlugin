from CTFd.plugins import register_plugin_assets_directory
from CTFd.plugins.challenges import CHALLENGE_CLASSES
from flask import Flask
from .container_challenge import ContainerChallenge
from .routes import register_app
from .logs import init_logs

def load(app: Flask):
    app.db.create_all()
    CHALLENGE_CLASSES["container"] = ContainerChallenge
    register_plugin_assets_directory(app, base_path="/plugins/containers/assets/")
    init_logs(app)

    # Get the blueprint from register_app and register it here
    containers_bp = register_app(app)
    app.register_blueprint(containers_bp)
