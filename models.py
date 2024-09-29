"""
This module defines the database models for the containers plugin in CTFd.
It includes models for container challenges, container information, and container settings.
"""

from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from CTFd.models import db
from CTFd.models import Challenges

class ContainerChallengeModel(Challenges):
    """
    Represents a container-based challenge in CTFd.

    This model extends the base Challenges model with additional fields
    specific to container challenges.
    """
    __mapper_args__ = {"polymorphic_identity": "container"}
    id = db.Column(
        db.Integer, db.ForeignKey("challenges.id", ondelete="CASCADE"), primary_key=True
    )  # Unique identifier for each container challenge.
    image = db.Column(db.Text)  # Docker image used for the container challenge.
    port = db.Column(db.Integer)  # Port number the container listens on.
    command = db.Column(db.Text, default="")  # Command to run inside the container.
    volumes = db.Column(db.Text, default="")  # Volume mappings for the container.

    # Dynamic challenge properties
    initial = db.Column(db.Integer, default=0)  # Initial point value for the challenge.
    minimum = db.Column(db.Integer, default=0)  # Minimum point value after decay.
    decay = db.Column(db.Integer, default=0)  # Rate of point decay over time.

    def __init__(self, *args, **kwargs):
        """
        Initialize a new ContainerChallengeModel instance.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        super(ContainerChallengeModel, self).__init__(**kwargs)
        self.value = kwargs["initial"]  # Set the initial point value from the given arguments.

class ContainerInfoModel(db.Model):
    """
    Represents information about a running container instance.

    This model stores details about container instances created for challenges,
    including which user or team the container belongs to.
    """
    __mapper_args__ = {"polymorphic_identity": "container_info"}
    container_id = db.Column(db.String(512), primary_key=True)  # Unique container ID.
    challenge_id = db.Column(
        db.Integer, db.ForeignKey("challenges.id", ondelete="CASCADE")
    )  # Associated challenge ID for the container.
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE")
    )  # ID of the user who owns the container.
    team_id = db.Column(
        db.Integer, db.ForeignKey("teams.id", ondelete="CASCADE")
    )  # ID of the team who owns the container.
    port = db.Column(db.Integer)  # Port number for the container instance.
    timestamp = db.Column(db.Integer)  # Creation timestamp of the container.
    expires = db.Column(db.Integer)  # Expiration timestamp for the container.

    # Relationships to link container to user, team, and challenge.
    user = db.relationship("Users", foreign_keys=[user_id])
    team = db.relationship("Teams", foreign_keys=[team_id])
    challenge = db.relationship(ContainerChallengeModel,
                                foreign_keys=[challenge_id])

class ContainerSettingsModel(db.Model):
    """
    Represents configuration settings for the containers plugin.

    This model stores key-value pairs for various settings related to
    container management in the CTFd platform.
    """
    key = db.Column(db.String(512), primary_key=True)  # Setting key.
    value = db.Column(db.Text)  # Setting value.

    @classmethod
    def apply_default_config(cls, key, value):
        """
        Set the default configuration for a container setting.

        Args:
            key (str): The setting key.
            value (str): The setting value.
        """
        # If the setting is not already in the database, add it as a new entry.
        if not cls.query.filter_by(key=key).first():
            db.session.add(cls(key=key, value=value))
