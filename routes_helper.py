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

def kill_container(container_manager, container_id, challenge_id, user_id):
    container: ContainerInfoModel = ContainerInfoModel.query.filter_by(
        container_id=container_id).first()

    try:
        log("containers_actions", format="[{date}|IP:{ip}|USER:{user_id}|CHALL:{challenge_id}] Killing container '{container_id}'",
                        user_id=user_id,
                        challenge_id=challenge_id,
                        container_id=container_id)
        container_manager.kill_container(container_id)
    except Exception as err:
        log("containers_errors", format="[{date}|IP:{ip}|USER:{user_id}|CHALL:{challenge_id}] Container '{container_id}' could not be killed ({error})",
                        user_id=user_id,
                        challenge_id=challenge_id,
                        container_id=container_id,
                        error=str(err))
        return {"error": "An error has occurred."}, 500

    db.session.delete(container)
    db.session.commit()

    log("containers_actions", format="[{date}|IP:{ip}|USER:{user_id}|CHALL:{challenge_id}] Container '{container_id}' killed",
                        user_id=user_id,
                        challenge_id=challenge_id,
                        container_id=container_id)
    return {"success": "Container killed"}

def renew_container(container_manager, challenge_id, user_id, team_id, docker_assignment):
    # Get the requested challenge
    challenge = ContainerChallenge.challenge_model.query.filter_by(
        id=challenge_id).first()

    # Make sure the challenge exists and is a container challenge
    if challenge is None:
        log("containers_errors", format="[{date}|IP:{ip}|USER:{user_id}|CHALL:{challenge_id}] Renewing container failed (Challenge not found)",
                        user_id=user_id,
                        challenge_id=challenge_id)
        return {"error": "An error has occurred."}, 500, 400

    if docker_assignment == "user" or "unlimited":
        running_container = ContainerInfoModel.query.filter_by(
            challenge_id=challenge_id,
            user_id=user_id).first()
    else:
        running_container = ContainerInfoModel.query.filter_by(
            challenge_id=challenge_id, team_id=team_id).first()

    if running_container is None:
        log("containers_errors", format="[{date}|IP:{ip}|USER:{user_id}|CHALL:{challenge_id}] Renew container failed (Container not found)",
            user_id=user_id,
            challenge_id=challenge_id)
        return {"error": "An error has occurred."}, 500

    try:
        running_container.expires = int(
            time.time() + container_manager.expiration_seconds)
    except Exception as err:
        log("containers_errors", format="[{date}|IP:{ip}|USER:{user_id}|CHALL:{challenge_id}] Renew container '{container_id}' failed (Database error : '{error}')",
                        user_id=user_id,
                        challenge_id=challenge_id,
                        container_id=running_container.container_id,
                        error=str(err))
        return {"error": "An error occrured."}

    db.session.commit()

    log("containers_actions", format="[{date}|IP:{ip}|USER:{user_id}|CHALL:{challenge_id}] Container '{container_id}' renewed",
                        user_id=user_id,
                        challenge_id=challenge_id,
                        container_id=running_container.container_id)
    return {"success": "Container renewed", "expires": running_container.expires}

def create_container(container_manager, challenge_id, user_id, team_id, docker_assignment):
    # Get the requested challenge
    challenge = ContainerChallenge.challenge_model.query.filter_by(
        id=challenge_id).first()

    # Make sure the challenge exists and is a container challenge
    if challenge is None:
        log("containers_errors", format="[{date}|IP:{ip}|TEAM:{team_id}|CHALL:{challenge_id}] Container creation failed (Challenge not found)",
                        team_id=team_id,
                        challenge_id=challenge_id)
        return {"error": "An error has occurred."}, 500, 400

    # Check for any existing containers for the team
    if docker_assignment == "user" or "unlimited":
        running_containers = ContainerInfoModel.query.filter_by(
        challenge_id=challenge.id, user_id=user_id)
        running_container = running_containers.first()
    else:
        running_containers = ContainerInfoModel.query.filter_by(
            challenge_id=challenge.id, team_id=team_id)
        running_container = running_containers.first()

    # If a container is already running, return it
    if running_container:
        # Check if Docker says the container is still running before returning it
        try:
            if container_manager.is_container_running(running_container.container_id):
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
        except Exception as err:
            log("containers_errors", format="[{date}|IP:{ip}|TEAM:{team_id}|CHALL:{challenge_id}] Container creation failed ({error})",
                            team_id=team_id,
                            challenge_id=challenge_id,
                            container_id=running_container.container_id,
                            error=str(err))
            return {"error": "An error has occurred."}, 500, 500

    running_containers_for_user = ContainerInfoModel.query.filter_by(team_id=team_id)
    running_container_for_user = running_containers_for_user.first()

    # Check if other container is running
    if docker_assignment == "user":
        running_containers_for_user = ContainerInfoModel.query.filter_by(user_id=user_id)
        running_container_for_user = running_containers_for_user.first()
    elif docker_assignment == "team":
        running_containers_for_user = ContainerInfoModel.query.filter_by(team_id=team_id)
        running_container_for_user = running_containers_for_user.first()
    else:
        running_container_for_user = None

    if running_container_for_user:
        challenge_of_running_container = ContainerChallenge.challenge_model.query.filter_by(id=running_container_for_user.challenge_id).first()
        log("containers_actions", format="[{date}|IP:{ip}|USER:{user_id}|CHALL:{challenge_id}] Container creation failled (Other instance already running)",
                        user_id=user_id,
                        challenge_id=challenge_id)
        return {"error": f"Stop other instance running ({challenge_of_running_container.name})"}, 400

    # Run a new Docker container
    try:
        created_container = container_manager.create_container(
            challenge.image, challenge.port, challenge.command, challenge.volumes)
    except Exception as err:
        log("containers_errors", format="[{date}|IP:{ip}|USER:{user_id}|CHALL:{challenge_id}] Container creation failed ({error})",
                        user_id=user_id,
                        challenge_id=challenge_id,
                        error=str(err))
        return {"error": "An error has occurred."}, 500

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
        user_id=user_id,
        team_id=team_id,
        port=port,
        timestamp=int(time.time()),
        expires=expires
    )
    db.session.add(new_container)
    db.session.commit()

    log("containers_actions", format="[{date}|IP:{ip}|USER:{user_id}|CHALL:{challenge_id}] Container '{container_id}' created",
                    user_id=user_id,
                    challenge_id=challenge_id,
                    container_id=created_container.id)
    return json.dumps({
        "status": "created",
        "hostname": challenge.connection_info,
        "port": port,
        "expires": expires
    })
