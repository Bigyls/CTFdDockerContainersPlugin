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
    )
    image = db.Column(db.Text)
    port = db.Column(db.Integer)
    command = db.Column(db.Text, default="")
    volumes = db.Column(db.Text, default="")

    # Dynamic challenge properties
    initial = db.Column(db.Integer, default=0)
    minimum = db.Column(db.Integer, default=0)
    decay = db.Column(db.Integer, default=0)

    def __init__(self, *args, **kwargs):
        """
        Initialize a new ContainerChallengeModel instance.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        super(ContainerChallengeModel, self).__init__(**kwargs)
        self.value = kwargs["initial"]

class ContainerInfoModel(db.Model):
    """
    Represents information about a running container instance.

    This model stores details about container instances created for challenges,
    including which user or team the container belongs to.
    """
    __mapper_args__ = {"polymorphic_identity": "container_info"}
    container_id = db.Column(db.String(512), primary_key=True)
    challenge_id = db.Column(
        db.Integer, db.ForeignKey("challenges.id", ondelete="CASCADE")
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE")
    )
    team_id = db.Column(
        db.Integer, db.ForeignKey("teams.id", ondelete="CASCADE")
    )
    port = db.Column(db.Integer)
    timestamp = db.Column(db.Integer)
    expires = db.Column(db.Integer)
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
    key = db.Column(db.String(512), primary_key=True)
    value = db.Column(db.Text)

    def __init__(self, key, value):
        """
        Initialize a new ContainerSettingsModel instance.

        Args:
            key (str): The setting key.
            value (str): The setting value.
        """
        self.key = key
        self.value = value

    def __repr__(self):
        """
        Return a string representation of the ContainerSettingsModel instance.

        Returns:
            str: A string representation of the model instance.
        """
        return "<ContainerSettingsModel {0} {1}>".format(self.key, self.value)
