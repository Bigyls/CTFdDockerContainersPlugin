"""
This module defines the routes and blueprint for the containers plugin in CTFd.
It handles container management operations such as running, requesting, renewing,
resetting, stopping, and purging containers, as well as administrative functions
like updating settings and viewing the container dashboard.
"""
import time
import datetime

from flask import Blueprint, request, Flask, render_template, url_for, redirect, flash, current_app

from CTFd.models import db
from CTFd.utils.decorators import authed_only, admins_only, during_ctf_time_only, ratelimit, require_verified_emails
from CTFd.utils.user import get_current_user

from .logs import log
from .models import ContainerInfoModel, ContainerSettingsModel
from .container_manager import ContainerManager
from .container_challenge import ContainerChallenge
from .routes_helper import format_time_filter, create_container, renew_container, kill_container

containers_bp = Blueprint(
    'containers', __name__, template_folder='templates', static_folder='assets', url_prefix='/containers')

def settings_to_dict(settings):
    """
    Convert settings objects to a dictionary.
    """
    return {setting.key: setting.value for setting in settings}

def register_app(app: Flask):
    """
    Register the containers blueprint with the Flask app.

    Args:
        app (Flask): The Flask application instance.

    Returns:
        Blueprint: The registered containers blueprint.
    """
    container_settings = settings_to_dict(ContainerSettingsModel.query.all())
    log("containers_debug", format="Registering containers blueprint with settings: {settings}",
        settings=container_settings)
    global container_manager
    container_manager = ContainerManager(container_settings, app)
    return containers_bp

def format_time_filter(timestamp):
    """
    Format a timestamp into a readable string.
    """
    return datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

containers_bp.app_template_filter("format_time")(format_time_filter)

@containers_bp.route('/api/running', methods=['POST'])
@authed_only
@during_ctf_time_only
@require_verified_emails
@ratelimit(method="POST", limit=100, interval=300, key_prefix='rl_running_container_post')
def route_running_container():
    """
    Check if a container is running for a given challenge.
    """
    user = get_current_user()
    log("containers_debug", format="Checking running container status")

    if request.json is None or request.json.get("chal_id") is None or user is None:
        log("containers_errors", format="Invalid request to /api/running")
        return {"error": "Invalid request"}, 400

    try:
        challenge = ContainerChallenge.challenge_model.query.filter_by(id=request.json.get("chal_id")).first()
        if challenge is None:
            log("containers_errors", format="CHALL_ID:{challenge_id}|Challenge not found during running container check",
                challenge_id=request.json.get("chal_id"))
            return {"error": "An error occured."}, 500

        docker_assignment = container_manager.settings.get("docker_assignment")
        log("containers_debug", format="CHALL_ID:{challenge_id}|Docker assignment mode: {mode}",
            challenge_id=challenge.id,
            mode=docker_assignment)

        if docker_assignment in ["user", "unlimited"]:
            running_container = ContainerInfoModel.query.filter_by(
                challenge_id=challenge.id,
                user_id=user.id).first()
        else:
            running_container = ContainerInfoModel.query.filter_by(
                challenge_id=challenge.id, team_id=user.team_id).first()

        if running_container:
            log("containers_actions", format="CHALL_ID:{challenge_id}|Container '{container_id}' already running",
                challenge_id=challenge.id,
                container_id=running_container.container_id)
            return {"status": "already_running", "container_id": request.json.get("chal_id")}, 200
        else:
            log("containers_actions", format="CHALL_ID:{challenge_id}|No running container found",
                challenge_id=challenge.id)
            return {"status": "stopped", "container_id": request.json.get("chal_id")}, 200

    except Exception as err:
        log("containers_errors", format="CHALL_ID:{challenge_id}|Error checking running container status ({error})",
            challenge_id=request.json.get("chal_id"),
            error=str(err))
        return {"error": "An error has occured."}, 500

@containers_bp.route('/api/request', methods=['POST'])
@authed_only
@during_ctf_time_only
@require_verified_emails
@ratelimit(method="POST", limit=100, interval=300, key_prefix='rl_request_container_post')
def route_request_container():
    """
    Request a new container for a challenge.
    """
    user = get_current_user()
    log("containers_debug", format="Requesting container")

    if request.json is None or request.json.get("chal_id") is None or user is None:
        log("containers_errors", format="Invalid request to /api/request")
        return {"error": "Invalid request"}, 400

    try:
        docker_assignment = container_manager.settings.get("docker_assignment")
        log("containers_debug", format="CHALL_ID:{challenge_id}|Docker assignment mode: {mode}",
            challenge_id=request.json.get("chal_id"),
            mode=docker_assignment)

        return create_container(container_manager, request.json.get("chal_id"), user.id, user.team_id, docker_assignment)
    except Exception as err:
        log("containers_errors", format="CHALL_ID:{challenge_id}|Error during container creation ({error})",
            challenge_id=request.json.get("chal_id"),
            error=str(err))
        return {"error": "An error has occured."}, 500

@containers_bp.route('/api/renew', methods=['POST'])
@authed_only
@during_ctf_time_only
@require_verified_emails
@ratelimit(method="POST", limit=100, interval=300, key_prefix='rl_renew_container_post')
def route_renew_container():
    """
    Renew an existing container for a challenge.
    """
    user = get_current_user()
    log("containers_debug", format="Requesting container renewal")

    if request.json is None or request.json.get("chal_id") is None or user is None:
        log("containers_errors", format="Invalid request to /api/renew")
        return {"error": "Invalid request"}, 400

    try:
        docker_assignment = container_manager.settings.get("docker_assignment")
        log("containers_debug", format="CHALL_ID:{challenge_id}|Docker assignment mode: {mode}",
            challenge_id=request.json.get("chal_id"),
            mode=docker_assignment)

        return renew_container(container_manager, request.json.get("chal_id"), user.id, user.team_id, docker_assignment)
    except Exception as err:
        log("containers_errors", format="CHALL_ID:{challenge_id}|Error during container renewal ({error})",
            challenge_id=request.json.get("chal_id"),
            error=str(err))
        return {"error": "An error has occurred."}, 500

@containers_bp.route('/api/reset', methods=['POST'])
@authed_only
@during_ctf_time_only
@require_verified_emails
@ratelimit(method="POST", limit=100, interval=300, key_prefix='rl_restart_container_post')
def route_restart_container():
    """
    Restart a container for a challenge.
    """
    user = get_current_user()
    log("containers_debug", format="Requesting container reset")

    if request.json is None or request.json.get("chal_id") is None or user is None:
        log("containers_errors", format="Invalid request to /api/reset")
        return {"error": "Invalid request"}, 400

    docker_assignment = container_manager.settings.get("docker_assignment")
    log("containers_debug", format="CHALL_ID:{challenge_id}|Docker assignment mode: {mode}",
        challenge_id=request.json.get("chal_id"),
        mode=docker_assignment)

    if docker_assignment in ["user", "unlimited"]:
        running_container = ContainerInfoModel.query.filter_by(
            challenge_id=request.json.get("chal_id"),
            user_id=user.id).first()
    else:
        running_container = ContainerInfoModel.query.filter_by(
            challenge_id=request.json.get("chal_id"), team_id=user.team_id).first()

    if running_container:
        log("containers_actions", format="CHALL_ID:{challenge_id}|Resetting container '{container_id}'",
            challenge_id=request.json.get("chal_id"),
            container_id=running_container.container_id)
        kill_container(container_manager, running_container.container_id, request.json.get("chal_id"))

    log("containers_actions", format="CHALL_ID:{challenge_id}|Recreating container",
        challenge_id=request.json.get("chal_id"))
    return create_container(container_manager, request.json.get("chal_id"), user.id, user.team_id, docker_assignment)

@containers_bp.route('/api/stop', methods=['POST'])
@authed_only
@during_ctf_time_only
@require_verified_emails
@ratelimit(method="POST", limit=100, interval=300, key_prefix='rl_stop_container_post')
def route_stop_container():
    """
    Stop a running container for a challenge.
    """
    user = get_current_user()
    log("containers_debug", format="Requesting container stop")

    if request.json is None or request.json.get("chal_id") is None or user is None:
        log("containers_errors", format="Invalid request to /api/stop")
        return {"error": "Invalid request"}, 400

    docker_assignment = container_manager.settings.get("docker_assignment")
    log("containers_debug", format="CHALL_ID:{challenge_id}|Docker assignment mode: {mode}",
        challenge_id=request.json.get("chal_id"),
        mode=docker_assignment)

    if docker_assignment in ["user", "unlimited"]:
        running_container = ContainerInfoModel.query.filter_by(
            challenge_id=request.json.get("chal_id"),
            user_id=user.id).first()
    else:
        running_container = ContainerInfoModel.query.filter_by(
            challenge_id=request.json.get("chal_id"), team_id=user.team_id).first()

    if running_container:
        log("containers_actions", format="CHALL_ID:{challenge_id}|Stopping container '{container_id}'",
            challenge_id=request.json.get("chal_id"),
            container_id=running_container.container_id)
        return kill_container(container_manager, running_container.container_id, request.json.get("chal_id"))

    log("containers_errors", format="CHALL_ID:{challenge_id}|No running container found to stop",
        challenge_id=request.json.get("chal_id"))
    return {"error": "No running container found."}, 400

@containers_bp.route('/api/kill', methods=['POST'])
@admins_only
def route_kill_container():
    """
    Admin route to kill a specific container.
    """
    log("containers_debug", format="Admin requesting container kill")

    if request.json is None or request.json.get("container_id") is None:
        log("containers_errors", format="Invalid request to /api/kill")
        return {"error": "Invalid request"}, 400

    log("containers_actions", format="Admin killing container '{container_id}'",
        container_id=request.json.get("container_id"))
    return kill_container(container_manager, request.json.get("container_id"), "N/A")

@containers_bp.route('/api/purge', methods=['POST'])
@admins_only
def route_purge_containers():
    """
    Admin route to purge all containers.
    """
    log("containers_actions", format="Requesting container purge")

    containers = ContainerInfoModel.query.all()
    for container in containers:
        try:
            log("containers_actions", format="Admin killing container'{container_id}'",
                container_id=container.container_id)
            kill_container(container_manager, container.container_id, "N/A")
        except Exception as err:
            log("containers_errors", format="Error during purging container '{container_id}' ({error})",
                container_id=container.container_id,
                error=str(err))

    log("containers_actions", format="Admin completed container purge")
    return {"success": "Purged all containers"}, 200

@containers_bp.route('/api/images', methods=['GET'])
@admins_only
def route_get_images():
    """
    Admin route to get a list of available Docker images.
    """
    log("containers_debug", format="Admin requesting Docker images list")
    try:
        images = container_manager.get_images()
        log("containers_actions", format="Admin successfully retrieved {count} Docker images",
                count=len(images))
        return {"images": images}, 200
    except Exception as err:
        log("containers_errors", format="Admin encountered error while fetching Docker images ({error})",
                error=str(err))
        return {"error": "An error has occurred."}, 500

@containers_bp.route('/api/settings/update', methods=['POST'])
@admins_only
def route_update_settings():
    """
    Admin route to update container settings.
    """
    log("containers_debug", format="Admin initiating settings update")

    required_fields = [
        "docker_base_url", "docker_hostname", "container_expiration",
        "container_maxmemory", "container_maxcpu", "docker_assignment"
    ]

    for field in required_fields:
        if request.form.get(field) is None:
            log("containers_errors", format="Admin settings update failed: Missing required field {field}",
                    field=field)
            return {"error": f"Missing required field: {field}"}, 400

    settings = {
        "docker_base_url": request.form.get("docker_base_url"),
        "docker_hostname": request.form.get("docker_hostname"),
        "container_expiration": request.form.get("container_expiration"),
        "container_maxmemory": request.form.get("container_maxmemory"),
        "container_maxcpu": request.form.get("container_maxcpu"),
        "docker_assignment": request.form.get("docker_assignment")
    }

    try:
        for key, value in settings.items():
            setting = ContainerSettingsModel.query.filter_by(key=key).first()
            if setting is None:
                # Create
                new_setting = ContainerSettingsModel(key=key, value=value)
                db.session.add(new_setting)
                log("containers_actions", format=f"Admin created '{key}' setting DB row")
            else:
                # Update
                old_value = setting.value
                if old_value != value:
                    setting.value = value
                    log("containers_actions", format="Admin updated '{key}' setting DB row ({old_value} => {new_value})",
                            key=key,
                            old_value=old_value,
                            new_value=value)
    except Exception as err:
        log("containers_errors", format="Admin encountered error while updating settings ({error})",
                error=str(err))
        return {"error": "An error has occurred."}, 500

    try:
        db.session.commit()
        log("containers_actions", format="Admin successfully committed settings to database")
    except Exception as err:
        db.session.rollback()
        log("containers_errors", format="Admin encountered error while committing settings ({error})",
                error=str(err))
        return {"error": "Failed to update settings in database"}, 500

    try:
        all_settings = ContainerSettingsModel.query.all()
        new_settings = settings_to_dict(all_settings)
        container_manager.settings = new_settings
        log("containers_actions", format="Admin completed settings update. New settings: {settings}",
                settings=container_manager.settings)
    except Exception as err:
        log("containers_errors", format="Admin encountered error while updating container_manager settings ({error})",
                error=str(err))
        return {"error": "Failed to update container manager settings"}, 500
    return redirect(url_for(".route_containers_dashboard"))

@containers_bp.route('/dashboard', methods=['GET'])
@admins_only
def route_containers_dashboard():
    """
    Admin route to view the containers dashboard.
    """
    admin_user = get_current_user()
    log("containers_actions", format="Admin accessing container dashboard", user_id=admin_user.id)
    try:
        running_containers = ContainerInfoModel.query.order_by(
            ContainerInfoModel.timestamp.desc()).all()
        log("containers_debug", format="Admin retrieved {count} containers from database",
            user_id=admin_user.id, count=len(running_containers))

        connected = False
        try:
            connected = container_manager.is_connected()
            log("containers_debug", format="Admin checked Docker daemon connection: {status}",
                user_id=admin_user.id, status="Connected" if connected else "Disconnected")
        except Exception as err:
            log("containers_errors", format="Admin encountered error checking Docker daemon connection: {error}",
                user_id=admin_user.id, error=str(err))

        for i, container in enumerate(running_containers):
            try:
                running_containers[i].is_running = container_manager.is_container_running(
                    container.container_id)
                log("containers_debug", format="Admin checked container '{container_id}' status: {status}",
                    user_id=admin_user.id, container_id=container.container_id,
                    status="Running" if running_containers[i].is_running else "Stopped")
            except Exception as err:
                log("containers_errors", format="Admin encountered error checking container '{container_id}' status: {error}",
                    user_id=admin_user.id, container_id=container.container_id, error=str(err))
                running_containers[i].is_running = False

        docker_assignment = container_manager.settings.get("docker_assignment")
        log("containers_debug", format="Admin retrieved Docker assignment mode: {mode}",
            user_id=admin_user.id, mode=docker_assignment)

        log("containers_debug", format="Admin rendering dashboard with {running_containers} containers and docker_assignment to {docker_assignment}",
            user_id=admin_user.id, running_containers=len(running_containers),
            docker_assignment=docker_assignment)

        return render_template('container_dashboard.html',
                               containers=running_containers,
                               connected=connected,
                               settings={'docker_assignment': docker_assignment})
    except Exception as err:
        log("containers_errors", format="Admin encountered error rendering container dashboard: {error}",
            user_id=admin_user.id, error=str(err))
        current_app.logger.error(f"Error in container dashboard: {str(err)}", exc_info=True)
        return "An error occurred while loading the dashboard. Please check the logs.", 500

@containers_bp.route('/settings', methods=['GET'])
@admins_only
def route_containers_settings():
    """
    Admin route to view and edit container settings.
    """
    running_containers = ContainerInfoModel.query.order_by(
        ContainerInfoModel.timestamp.desc()).all()
    settings = settings_to_dict(ContainerSettingsModel.query.all())
    log("containers_actions", format="Admin Container settings called")
    return render_template('container_settings.html', settings=settings)
