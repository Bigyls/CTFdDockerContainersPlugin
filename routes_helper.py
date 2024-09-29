"""
This module provides utility functions for managing containers in the CTFd platform.
It includes functions for killing, renewing, and creating containers, as well as
helper functions for formatting time and converting settings to a dictionary.
"""

import time
import json
import datetime

from CTFd.models import db

from .logs import log
from .models import ContainerInfoModel
from .container_challenge import ContainerChallenge

def settings_to_dict(settings):
    """
    Convert a list of settings objects to a dictionary.

    Args:
        settings (list): A list of setting objects retrieved from the database.

    Returns:
        dict: A dictionary with setting keys as dictionary keys and their corresponding values.
    """
    return {
        setting.key: setting.value for setting in settings
    }

def format_time_filter(unix_seconds):
    """
    Convert Unix timestamp to ISO format string, including the current timezone.

    Args:
        unix_seconds (int): Unix timestamp in seconds since the epoch.

    Returns:
        str: ISO formatted date-time string with timezone information.
    """
    return datetime.datetime.fromtimestamp(unix_seconds, tz=datetime.datetime.now(
        datetime.timezone.utc).astimezone().tzinfo).isoformat()

def kill_container(container_manager, container_id, challenge_id):
    """
    Kill a running container and remove its record from the database.

    Args:
        container_manager: The container manager object responsible for managing Docker containers.
        container_id (str): The ID of the container to terminate.
        challenge_id (int): The ID of the associated challenge to log for tracking purposes.

    Returns:
        tuple: A dictionary with a success or error message and an HTTP status code.
    """
    # Log the initiation of the container termination process
    log("containers_debug", format="CHALL_ID:{challenge_id}|Initiating container kill process for container '{container_id}'",
            challenge_id=challenge_id,
            container_id=container_id)

    # Retrieve the container information from the database
    container = ContainerInfoModel.query.filter_by(container_id=container_id).first()

    # If the container does not exist in the database, log an error and return a 400 response
    if not container:
        log("containers_errors", format="CHALL_ID:{challenge_id}|Container '{container_id}' not found in database",
                challenge_id=challenge_id,
                container_id=container_id)
        return {"error": "Container not found"}, 400

    try:
        # Attempt to kill the container using the Docker manager
        log("containers_actions", format="CHALL_ID:{challenge_id}|Killing container '{container_id}'",
                challenge_id=challenge_id,
                container_id=container_id)
        container_manager.kill_container(container_id)
        log("containers_debug", format="CHALL_ID:{challenge_id}|Container '{container_id}' successfully killed by Docker",
                challenge_id=challenge_id,
                container_id=container_id)
    except Exception as err:
        # Log and return an error message if the container could not be terminated
        log("containers_errors", format="CHALL_ID:{challenge_id}|Failed to kill container '{container_id}' ({error})",
                challenge_id=challenge_id,
                container_id=container_id,
                error=str(err))
        return {"error": "Failed to kill container"}, 500

    try:
        # Remove the container record from the database after successful termination
        log("containers_debug", format="CHALL_ID:{challenge_id}|Removing container '{container_id}' from database",
                challenge_id=challenge_id,
                container_id=container_id)
        db.session.delete(container)
        db.session.commit()
        log("containers_debug", format="CHALL_ID:{challenge_id}|Container '{container_id}' successfully removed from database",
                challenge_id=challenge_id,
                container_id=container_id)
    except Exception as db_err:
        # Handle any database errors during the removal process
        log("containers_errors", format="CHALL_ID:{challenge_id}|Failed to remove container '{container_id}' from database ({error})",
                challenge_id=challenge_id,
                container_id=container_id,
                error=str(db_err))
        return {"error": "Failed to update database"}, 500

    # Log the successful removal of the container and return a success response
    log("containers_actions", format="CHALL_ID:{challenge_id}|Container '{container_id}' successfully killed and removed",
            challenge_id=challenge_id,
            container_id=container_id)
    return {"success": "Container killed and removed"}

def renew_container(container_manager, challenge_id, user_id, team_id, docker_assignment):
    """
    Renew the expiration time of a running container.

    Args:
        container_manager: The container manager object responsible for managing Docker containers.
        challenge_id (int): The ID of the associated challenge to be renewed.
        user_id (int): The ID of the user who owns the container.
        team_id (int): The ID of the team that owns the container.
        docker_assignment (str): The assignment mode for Docker containers (e.g., 'user' or 'team').

    Returns:
        tuple: A dictionary with a success message and new expiration time or an error message and HTTP status code.
    """
    # Log the initiation of the container renewal process
    log("containers_debug", format="CHALL_ID:{challenge_id}|Initiating container renewal process",
            challenge_id=challenge_id)

    # Retrieve the challenge object associated with the given challenge ID
    challenge = ContainerChallenge.challenge_model.query.filter_by(id=challenge_id).first()

    # If the challenge does not exist, log an error and return a 400 response
    if challenge is None:
        log("containers_errors", format="CHALL_ID:{challenge_id}|Renewing container failed (Challenge not found)",
                challenge_id=challenge_id)
        return {"error": "Challenge not found"}, 400

    # Log the Docker assignment mode being used
    log("containers_debug", format="CHALL_ID:{challenge_id}|Docker assignment mode: {mode}",
            challenge_id=challenge_id,
            mode=docker_assignment)

    # Determine the container to renew based on the assignment mode ('user' or 'team')
    if docker_assignment in ["user", "unlimited"]:
        running_container = ContainerInfoModel.query.filter_by(
            challenge_id=challenge_id,
            user_id=user_id).first()
    else:
        running_container = ContainerInfoModel.query.filter_by(
            challenge_id=challenge_id, team_id=team_id).first()

    # If the container does not exist, log an error and return a 400 response
    if running_container is None:
        log("containers_errors", format="CHALL_ID:{challenge_id}|Renew container failed (Container not found)",
                challenge_id=challenge_id)
        return {"error": "Container not found"}, 400

    try:
        # Update the expiration time of the container and commit changes to the database
        new_expiration = int(time.time() + container_manager.expiration_seconds)
        old_expiration = running_container.expires
        running_container.expires = new_expiration

        log("containers_debug", format="CHALL_ID:{challenge_id}|Updating container '{container_id}' expiration: {old_exp} -> {new_exp}",
                challenge_id=challenge_id,
                container_id=running_container.container_id,
                old_exp=old_expiration,
                new_exp=new_expiration)

        db.session.commit()

        # Log and return a success message with the new expiration time
        log("containers_debug", format="CHALL_ID:{challenge_id}|Container '{container_id}' renewed. New expiration: {new_exp}",
                challenge_id=challenge_id, 
                container_id=running_container.container_id,
                new_exp=new_expiration)

        return {"success": "Container renewed", "expires": new_expiration}
    except Exception as err:
        # Log and return an error message if the renewal process fails
        log("containers_errors", format="CHALL_ID:{challenge_id}|Renew container '{container_id}' failed ({error})",
                challenge_id=challenge_id,
                container_id=running_container.container_id,
                error=str(err))
        return {"error": "Failed to renew container"}, 500

def create_container(container_manager, challenge_id, user_id, team_id, docker_assignment):
    """
    Create a new container for a challenge.

    Args:
        container_manager: The container manager object.
        challenge_id (int): The ID of the associated challenge.
        user_id (int): The ID of the user.
        team_id (int): The ID of the team.
        docker_assignment (str): The docker assignment mode.

    Returns:
        str: A JSON string containing the container creation result.
    """
    # Log the start of the container creation process for a given challenge ID
    log("containers_debug", format="CHALL_ID:{challenge_id}|Initiating container creation process",
            challenge_id=challenge_id)

    # Retrieve the challenge object from the database using the provided challenge_id
    challenge = ContainerChallenge.challenge_model.query.filter_by(id=challenge_id).first()

    # If the challenge is not found, log an error and return a 400 response
    if challenge is None:
        log("containers_errors", format="CHALL_ID:{challenge_id}|Container creation failed (Challenge not found)",
                challenge_id=challenge_id)
        return {"error": "Challenge not found"}, 400

    # Log the Docker assignment mode being used
    log("containers_debug", format="CHALL_ID:{challenge_id}|Docker assignment mode: {mode}",
            challenge_id=challenge_id,
            mode=docker_assignment)

    running_containers_for_user = None

    # Determine the running containers to check based on the docker_assignment mode (user or team)
    if docker_assignment in ["user", "unlimited"]:
        running_containers = ContainerInfoModel.query.filter_by(
            challenge_id=challenge.id, user_id=user_id)
    elif docker_assignment == "team":
        running_containers = ContainerInfoModel.query.filter_by(
            challenge_id=challenge.id, team_id=team_id)

    # Check if there is already a container running for the given challenge and user/team
    running_container = running_containers.first()

    if running_container:
        try:
            # If the container is running, log the status and return the container's information
            if container_manager.is_container_running(running_container.container_id):
                log("containers_actions", format="CHALL_ID:{challenge_id}|Container '{container_id}' already running",
                        challenge_id=challenge_id,
                        container_id=running_container.container_id)
                return json.dumps({
                    "status": "already_running",
                    "hostname": challenge.connection_info,
                    "port": running_container.port,
                    "expires": running_container.expires
                })
            else:
                # If the container is not running, remove it from the database and proceed with creation
                log("containers_debug", format="CHALL_ID:{challenge_id}|Container '{container_id}' not running, removing from database",
                        challenge_id=challenge_id, container_id=running_container.container_id)
                db.session.delete(running_container)
                db.session.commit()
        except Exception as err:
            # Handle errors when checking the container status or deleting it from the database
            log("containers_errors", format="CHALL_ID:{challenge_id}|Error checking container '{container_id}' ({error})",
                    challenge_id=challenge_id, container_id=running_container.container_id, error=str(err))
            return {"error": "Error checking container status"}, 500

    # Check if there are other running containers for the same user/team
    if docker_assignment == "user":
        running_containers_for_user = ContainerInfoModel.query.filter_by(user_id=user_id)
    elif docker_assignment == "team":
        running_containers_for_user = ContainerInfoModel.query.filter_by(team_id=team_id)
    else:
        running_container_for_user = None

    # Retrieve the first container running for the user/team, if any
    running_container_for_user = running_containers_for_user.first() if running_containers_for_user else None

    # If another container is already running for a different challenge, return an error
    if running_container_for_user:
        challenge_of_running_container = ContainerChallenge.challenge_model.query.filter_by(id=running_container_for_user.challenge_id).first()
        log("containers_errors", format="CHALL_ID:{challenge_id}|Container creation failed (Other instance '{other_container_id}' for challenge '{other_challenge_name}' already running)",
                challenge_id=challenge_id,
                other_container_id=running_container_for_user.container_id,
                other_challenge_name=challenge_of_running_container.name)
        return {"error": f"Stop other instance running ({challenge_of_running_container.name})"}, 400

    try:
        # Attempt to create a new Docker container using the container manager
        log("containers_debug", format="CHALL_ID:{challenge_id}|Creating new Docker container",
                challenge_id=challenge_id)
        created_container = container_manager.create_container(
            challenge.image, challenge.port, challenge.command, challenge.volumes)
    except Exception as err:
        # If the container creation fails, log the error and return a 500 response
        log("containers_errors", format="CHALL_ID:{challenge_id}|Container creation failed: {error}",
                challenge_id=challenge_id,
                error=str(err))
        return {"error": "Failed to create container"}, 500

    # Retrieve the port assigned to the created container
    port = container_manager.get_container_port(created_container.id)

    # If the port cannot be obtained, log the error and return an error response
    if port is None:
        log("containers_errors", format="CHALL_ID:{challenge_id}|Could not get port for container '{container_id}'",
                challenge_id=challenge_id,
                container_id=created_container.id)
        return json.dumps({"status": "error", "error": "Could not get port"})

    # Calculate the expiration time for the new container
    expires = int(time.time() + container_manager.expiration_seconds)

    # Create a new database entry for the container
    new_container = ContainerInfoModel(
        container_id=created_container.id,
        challenge_id=challenge.id,
        user_id=user_id,
        team_id=team_id,
        port=port,
        timestamp=int(time.time()),
        expires=expires
    )

    try:
        # Add the new container record to the database and commit the changes
        db.session.add(new_container)
        db.session.commit()
        log("containers_actions", format="CHALL_ID:{challenge_id}|Container '{container_id}' created and added to database",
                challenge_id=challenge_id,
                container_id=created_container.id)
    except Exception as db_err:
        # Handle any database errors during the insertion of the new container record
        log("containers_errors", format="CHALL_ID:{challenge_id}|Failed to add container '{container_id}' to database: {error}",
                challenge_id=challenge_id,
                container_id=created_container.id,
                error=str(db_err))
        return {"error": "Failed to save container information"}, 500

    # Log the successful completion of the container creation process and return the container's information
    log("containers_debug", format="CHALL_ID:{challenge_id}|Container '{container_id}' creation process completed",
            challenge_id=challenge_id, container_id=created_container.id)
    return json.dumps({
        "status": "created",
        "hostname": challenge.connection_info,
        "port": port,
        "expires": expires
    })
