import time
import json
import datetime

from flask import current_app

from CTFd.models import db
from CTFd.utils.logging import log

from .models import ContainerInfoModel, ContainerSettingsModel
from .container_manager import ContainerManager, ContainerException
from .container_challenge import ContainerChallenge

def settings_to_dict(settings):
    return {
        setting.key: setting.value for setting in settings
    }

def format_time_filter(unix_seconds):
    return datetime.datetime.fromtimestamp(unix_seconds, tz=datetime.datetime.now(
        datetime.timezone.utc).astimezone().tzinfo).isoformat()

def kill_container(container_manager, container_id):
    container: ContainerInfoModel = ContainerInfoModel.query.filter_by(
        container_id=container_id).first()

    try:
        container_manager.kill_container(container_id)
    except ContainerException:
        log("containers", format="[{date}|IP:{ip}|CHALL:{challenge_id}] Container could not be killed (Bad docker initialization settings)",
                        container_id=container_id)
        return {"error": "Docker is not initialized. Please check your settings."}

    db.session.delete(container)

    db.session.commit()
    log("containers", format="[{date}|IP:{ip}] Container '{container_id}' killed",
                    container_id=container_id)
    return {"success": "Container killed"}

def renew_container(container_manager, chal_id, user_or_team_id):
    # Get the requested challenge
    challenge = ContainerChallenge.challenge_model.query.filter_by(
        id=chal_id).first()

    # Make sure the challenge exists and is a container challenge
    if challenge is None:
        log("containers", format="[{date}|IP:{ip}|USER/TEAM:{user_or_team_id}|CHALL:{challenge_id}] Renew container failed (Challenge not found)",
                        user_or_team_id=user_or_team_id,
                        challenge_id=chal_id)
        return {"error": "Challenge not found"}, 400

    running_container = ContainerInfoModel.query.filter(
        (ContainerInfoModel.challenge_id == challenge.id) &
        ((ContainerInfoModel.user_id == user_or_team_id) | (ContainerInfoModel.team_id == user_or_team_id))
    ).first()

    if running_container is None:
        log("containers", format="[{date}|IP:{ip}|USER/TEAM:{user_or_team_id}|CHALL:{challenge_id}] Renew container failed (Container not found)",
            user_or_team_id=user_or_team_id,
            challenge_id=chal_id)
        return {"error": "Container not found, try resetting the container."}

    try:
        running_container.expires = int(
            time.time() + container_manager.expiration_seconds)
        db.session.commit()
    except ContainerException as err:
        log("containers", format="[{date}|IP:{ip}|USER/TEAM:{user_or_team_id}|CHALL:{challenge_id}] Renew container '{container_id}' failed (Database error : '{error}')",
                        user_or_team_id=user_or_team_id,
                        challenge_id=chal_id,
                        container_id=running_container.container_id,
                        error=str(err))
        return {"error": "Database error occurred, please try again."}

    log("containers", format="[{date}|IP:{ip}|USER/TEAM:{user_or_team_id}|CHALL:{challenge_id}] Container '{container_id}' renewed",
                    user_or_team_id=user_or_team_id,
                    challenge_id=chal_id,
                    container_id=running_container.container_id)
    return {"success": "Container renewed", "expires": running_container.expires}

def create_container(container_manager, chal_id, user_or_team_id, is_team):
    # Get the requested challenge
    challenge = ContainerChallenge.challenge_model.query.filter_by(
        id=chal_id).first()

    # Make sure the challenge exists and is a container challenge
    if challenge is None:
        log("containers", format="[{date}|IP:{ip}|USER/TEAM:{user_or_team_id}|CHALL:{challenge_id}] Container creation failed (Challenge not found)",
                        user_or_team_id=user_or_team_id,
                        challenge_id=chal_id)
        return {"error": "Challenge not found"}, 400

    # Check for any existing containers for the user or team
    if is_team:
        running_container = ContainerInfoModel.query.filter_by(
            challenge_id=challenge.id, team_id=user_or_team_id).first()
    else:
        running_container = ContainerInfoModel.query.filter_by(
            challenge_id=challenge.id, user_id=user_or_team_id).first()

    # If a container is already running for the user or team, return it
    if running_container:
        # Check if Docker says the container is still running before returning it
        try:
            if container_manager.is_container_running(
                    running_container.container_id):
                return json.dumps({
                    "status": "already_running",
                    "hostname": challenge.connection_info,
                    "port": running_container.port,
                    "expires": running_container.expires
                })
            else:
                # Container is not running, it must have died or been killed,
                # remove it from the database and create a new one
                db.session.delete(running_container)
                db.session.commit()
        except ContainerException as err:
            log("containers", format="[{date}|IP:{ip}|USER/TEAM:{user_or_team_id}|CHALL:{challenge_id}] Container creation failed ({error})",
                            user_or_team_id=user_or_team_id,
                            challenge_id=chal_id,
                            container_id=running_container.container_id,
                            error=str(err))
            return {"error": str(err)}, 500

    # Run a new Docker container
    try:
        created_container = container_manager.create_container(
            challenge.image, challenge.port, challenge.command, challenge.volumes)
    except ContainerException as err:
        log("containers", format="[{date}|IP:{ip}|USER/TEAM:{user_or_team_id}|CHALL:{challenge_id}] Container creation failed ({error})",
                        user_or_team_id=user_or_team_id,
                        challenge_id=chal_id,
                        error=str(err))
        return {"error": str(err)}

    # Fetch the random port Docker assigned
    port = container_manager.get_container_port(created_container.id)

    # Port may be blank if the container failed to start
    if port is None:
        return json.dumps({
            "status": "error",
            "error": "Could not get port"
        })

    expires = int(time.time() + container_manager.expiration_seconds)

    # Insert the new container into the database
    new_container = ContainerInfoModel(
        container_id=created_container.id,
        challenge_id=challenge.id,
        user_id=None if is_team else user_or_team_id,
        team_id=user_or_team_id if is_team else None,
        port=port,
        timestamp=int(time.time()),
        expires=expires
    )
    db.session.add(new_container)
    db.session.commit()

    log("containers", format="[{date}|IP:{ip}|USER/TEAM:{user_or_team_id}|CHALL:{challenge_id}] Container '{container_id}' created",
                    user_or_team_id=user_or_team_id,
                    challenge_id=chal_id,
                    container_id=created_container.id)
    return json.dumps({
        "status": "created",
        "hostname": challenge.connection_info,
        "port": port,
        "expires": expires
    })
