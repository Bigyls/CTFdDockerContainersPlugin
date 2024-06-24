from CTFd.plugins import register_plugin_assets_directory
from CTFd.plugins.challenges import CHALLENGE_CLASSES

from .container_challenge import ContainerChallenge
from .routes import register_app

CHALLENGE_CLASSES["container"] = ContainerChallenge

def load(app):
    app.db.create_all()
    register_plugin_assets_directory(app, base_path="/plugins/containers/assets/")
    register_app(app)
