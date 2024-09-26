"""
This module defines the ContainerChallenge class, which extends BaseChallenge
to provide functionality for container-based challenges in CTFd.
"""

from __future__ import division

import math

from CTFd.models import db, Solves
from CTFd.plugins.challenges import BaseChallenge
from CTFd.utils.modes import get_model

from .models import ContainerChallengeModel

class ContainerChallenge(BaseChallenge):
    """
    ContainerChallenge class for handling container-based challenges in CTFd.

    This class extends BaseChallenge and provides methods for reading,
    updating, and solving container challenges, as well as calculating
    their dynamic point values.
    """

    id = "container"  # Unique identifier used to register challenges
    name = "container"  # Name of a challenge type
    templates = {  # Handlebars templates used for each aspect of challenge editing & viewing
        "create": "/plugins/containers/assets/create.html",
        "update": "/plugins/containers/assets/update.html",
        "view": "/plugins/containers/assets/view.html",
    }
    scripts = {  # Scripts that are loaded when a template is loaded
        "create": "/plugins/containers/assets/create.js",
        "update": "/plugins/containers/assets/update.js",
        "view": "/plugins/containers/assets/view.js",
    }
    # Route at which files are accessible. This must be registered using register_plugin_assets_directory()
    route = "/plugins/containers/assets/"

    challenge_model = ContainerChallengeModel

    @classmethod
    def read(cls, challenge):
        """
        Access the data of a challenge in a format processable by the front end.

        Args:
            challenge: The challenge object to read data from.

        Returns:
            dict: A dictionary containing the challenge data for frontend processing.
        """
        data = {
            "id": challenge.id,
            "name": challenge.name,
            "value": challenge.value,
            "image": challenge.image,
            "port": challenge.port,
            "command": challenge.command,
            "initial": challenge.initial,
            "decay": challenge.decay,
            "minimum": challenge.minimum,
            "description": challenge.description,
            "connection_info": challenge.connection_info,
            "category": challenge.category,
            "state": challenge.state,
            "max_attempts": challenge.max_attempts,
            "type": challenge.type,
            "type_data": {
                "id": cls.id,
                "name": cls.name,
                "templates": cls.templates,
                "scripts": cls.scripts,
            },
        }
        return data

    @classmethod
    def calculate_value(cls, challenge):
        """
        Calculate the dynamic point value for a challenge based on solve count.

        Args:
            challenge: The challenge object to calculate value for.

        Returns:
            The challenge object with updated value.
        """
        Model = get_model()

        solve_count = (
            Solves.query.join(Model, Solves.account_id == Model.id)
            .filter(
                Solves.challenge_id == challenge.id,
                Model.hidden == False,
                Model.banned == False,
            )
            .count()
        )

        # If the solve count is 0 we shouldn't manipulate the solve count to
        # let the math update back to normal
        if solve_count != 0:
            # We subtract -1 to allow the first solver to get max point value
            solve_count -= 1

        # It is important that this calculation takes into account floats.
        # Hence this file uses from __future__ import division
        value = (
            ((challenge.minimum - challenge.initial) / (challenge.decay ** 2))
            * (solve_count ** 2)
        ) + challenge.initial

        value = math.ceil(value)

        if value < challenge.minimum:
            value = challenge.minimum

        challenge.value = value
        db.session.commit()
        return challenge

    @classmethod
    def update(cls, challenge, request):
        """
        Update the information associated with a challenge.

        Args:
            challenge: The challenge object to update.
            request: The request object containing the update data.

        Returns:
            The updated challenge object with recalculated value.
        """
        data = request.form or request.get_json()

        for attr, value in data.items():
            # We need to set these to floats so that the next operations don't operate on strings
            if attr in ("initial", "minimum", "decay"):
                value = float(value)
            setattr(challenge, attr, value)

        return ContainerChallenge.calculate_value(challenge)

    @classmethod
    def solve(cls, user, team, challenge, request):
        """
        Handle the solving of a challenge by a user or team.

        Args:
            user: The user solving the challenge.
            team: The team solving the challenge.
            challenge: The challenge being solved.
            request: The request object associated with the solve attempt.

        Returns:
            None
        """
        super().solve(user, team, challenge, request)

        ContainerChallenge.calculate_value(challenge)
