import time
import json
import datetime

from flask import Blueprint, request, Flask, render_template, url_for, redirect, flash, current_app

from CTFd.models import db
from CTFd.utils.decorators import authed_only, admins_only, during_ctf_time_only, ratelimit, require_verified_emails
from CTFd.utils.user import get_current_user
from CTFd.utils.logging import log

from .models import ContainerInfoModel, ContainerSettingsModel
from .container_manager import ContainerManager, ContainerException
from .container_challenge import ContainerChallenge
from .routes_helper import format_time_filter, create_container, renew_container, kill_container

containers_bp = Blueprint(
    'containers', __name__, template_folder='templates', static_folder='assets', url_prefix='/containers')

def settings_to_dict(settings):
    return {setting.key: setting.value for setting in settings}

def register_app(app: Flask):
    container_settings = settings_to_dict(ContainerSettingsModel.query.all())
    global container_manager
    container_manager = ContainerManager(container_settings, app)
    return containers_bp

def format_time_filter(timestamp):
    return datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

containers_bp.app_template_filter("format_time")(format_time_filter)

@containers_bp.route('/api/running', methods=['POST'])
@authed_only
@during_ctf_time_only
@require_verified_emails
@ratelimit(method="POST", limit=100, interval=300, key_prefix='rl_running_container_post')
def route_running_container():
    user = get_current_user()

    if request.json is None or request.json.get("chal_id") is None or user is None:
        return {"error": "Invalid request"}, 400

    try:
        challenge = ContainerChallenge.challenge_model.query.filter_by(id=request.json.get("chal_id")).first()
        if challenge is None:
            log("containers_errors", format="[{date}|IP:{ip}|USER:{user_id}|CHALL:{challenge_id}] Challenge not found during checking if container is running",
                            user_id=user.id,
                            challenge_id=request.json.get("chal_id"))
            return {"error": "An error occured"}, 400

        docker_assignment = container_manager.settings.get("docker_assignment")

        if docker_assignment in ["user", "unlimited"]:
            running_container = ContainerInfoModel.query.filter_by(
                challenge_id=challenge.id,
                user_id=user.id).first()
        else:
            running_container = ContainerInfoModel.query.filter_by(
                challenge_id=challenge.id, team_id=user.team_id).first()

        if running_container:
            return {"status": "already_running", "container_id": request.json.get("chal_id")}, 200
        else:
            return {"status": "stopped", "container_id": request.json.get("chal_id")}, 200

    except Exception as err:
        log("containers_errors", format="[{date}|IP:{ip}|USER:{user_id}|CHALL:{challenge_id}] Error checking if container is running ({error})",
                        user_id=user.id,
                        challenge_id=request.json.get("chal_id"),
                        error=str(err))
        return {"error": "An error has occurred."}, 500, 500

@containers_bp.route('/api/request', methods=['POST'])
@authed_only
@during_ctf_time_only
@require_verified_emails
@ratelimit(method="POST", limit=100, interval=300, key_prefix='rl_request_container_post')
def route_request_container():
    user = get_current_user()

    if request.json is None or request.json.get("chal_id") is None or user is None:
        return {"error": "Invalid request"}, 400

    try:
        docker_assignment = container_manager.settings.get("docker_assignment")
        log("containers_actions", format="[{date}|IP:{ip}|USER:{user_id}|CHALL:{challenge_id}] Creating container",
                        user_id=user.id,
                        challenge_id=request.json.get("chal_id"))
        return create_container(container_manager, request.json.get("chal_id"), user.id, user.team_id, docker_assignment)
    except Exception as err:
        log("containers_errors", format="[{date}|IP:{ip}|USER:{user_id}|CHALL:{challenge_id}] Error during creating container ({error})",
                        user_id=user.id,
                        challenge_id=request.json.get("chal_id"),
                        error=str(err))
        return {"error": "An error has occurred."}, 500, 500

@containers_bp.route('/api/renew', methods=['POST'])
@authed_only
@during_ctf_time_only
@require_verified_emails
@ratelimit(method="POST", limit=100, interval=300, key_prefix='rl_renew_container_post')
def route_renew_container():
    user = get_current_user()

    if request.json is None or request.json.get("chal_id") is None or user is None:
        return {"error": "Invalid request"}, 400

    try:
        docker_assignment = container_manager.settings.get("docker_assignment")
        log("containers_actions", format="[{date}|IP:{ip}|USER:{user_id}|CHALL:{challenge_id}] Renewing container",
                        user_id=user.id,
                        challenge_id=request.json.get("chal_id"))
        return renew_container(container_manager, request.json.get("chal_id"), user.id, user.team_id, docker_assignment)
    except Exception as err:
        log("containers_errors", format="[{date}|IP:{ip}|USER:{user_id}|CHALL:{challenge_id}] Error during renewing container ({error})",
                        user_id=user.id,
                        challenge_id=request.json.get("chal_id"),
                        error=str(err))
        return {"error": "An error has occurred."}, 500, 500

@containers_bp.route('/api/reset', methods=['POST'])
@authed_only
@during_ctf_time_only
@require_verified_emails
@ratelimit(method="POST", limit=100, interval=300, key_prefix='rl_restart_container_post')
def route_restart_container():
    user = get_current_user()

    if request.json is None or request.json.get("chal_id") is None or user is None:
        log("containers_errors", format="[{date}|IP:{ip}|USER:{user_id}|CHALL:{challenge_id}] Invalid request",
                user_id=user.id,
                challenge_id=request.json.get("chal_id"))
        return {"error": "Invalid request"}, 400

    docker_assignment = container_manager.settings.get("docker_assignment")

    if docker_assignment in ["user", "unlimited"]:
        running_container = ContainerInfoModel.query.filter_by(
            challenge_id=request.json.get("chal_id"),
            user_id=user.id).first()
    else:
        running_container = ContainerInfoModel.query.filter_by(
            challenge_id=request.json.get("chal_id"), team_id=user.team_id).first()

    if running_container:
        log("containers_actions", format="[{date}|IP:{ip}|USER:{user_id}|CHALL:{challenge_id}] Resetting container",
                        user_id=user.id,
                        challenge_id=request.json.get("chal_id"))
        kill_container(container_manager, running_container.container_id, request.json.get("chal_id"), user.id)

    log("containers_actions", format="[{date}|IP:{ip}|USER:{user_id}|CHALL:{challenge_id}] Recreating container",
                    user_id=user.id,
                    challenge_id=request.json.get("chal_id"))
    return create_container(container_manager, request.json.get("chal_id"), user.id, user.team_id, docker_assignment)

@containers_bp.route('/api/stop', methods=['POST'])
@authed_only
@during_ctf_time_only
@require_verified_emails
@ratelimit(method="POST", limit=100, interval=300, key_prefix='rl_stop_container_post')
def route_stop_container():
    user = get_current_user()
    if request.json is None or request.json.get("chal_id") is None or user is None:
        log("containers_errors", format="[{date}|IP:{ip}] Invalid request")
        return {"error": "Invalid request"}, 400

    docker_assignment = container_manager.settings.get("docker_assignment")

    if docker_assignment in ["user", "unlimited"]:
        running_container = ContainerInfoModel.query.filter_by(
            challenge_id=request.json.get("chal_id"),
            user_id=user.id).first()
    else:
        running_container = ContainerInfoModel.query.filter_by(
            challenge_id=request.json.get("chal_id"), team_id=user.team_id).first()

    if running_container:
        log("containers_actions", format="[{date}|IP:{ip}] Stopping container '{container_id}'",
                container_id=running_container.container_id)
        return kill_container(container_manager, running_container.container_id, request.json.get("chal_id"), user.id)
    return {"error": "An error has occured."}, 400

@containers_bp.route('/api/kill', methods=['POST'])
@admins_only
def route_kill_container():
    if request.json is None or request.json.get("container_id") is None:
        log("containers_errors", format="[{date}|IP:{ip}|USER:Admin] Invalid request")
        return {"error": "Invalid request"}, 400

    log("containers_actions", format="[{date}|IP:{ip}] Admin killing container")
    return kill_container(container_manager, request.json.get("container_id"), "N/A", 1)

@containers_bp.route('/api/purge', methods=['POST'])
@admins_only
def route_purge_containers():
    containers = ContainerInfoModel.query.all()
    for container in containers:
        try:
            log("containers_actions", format="[{date}|IP:{ip}] Admin killing container '{container_id}'",
                    container_id=container.container_id)
            kill_container(container_manager, container.container_id, "N/A", 1)
        except Exception as err:
            log("containers_errors", format="[{date}|IP:{ip}|USER:Admin] Error during purging containers ({error})",
                    error=str(err))
        pass
    log("containers_actions", format="[{date}|IP:{ip}] Admin purged all containers")
    return {"success": "Purged all containers"}, 200

@containers_bp.route('/api/images', methods=['GET'])
@admins_only
def route_get_images():
    try:
        images = container_manager.get_images()
    except Exception as err:
        log("containers_errors", format="[{date}|IP:{ip}|USER:Admin] Error during fetching images ({error})",
                                    error=str(err))
        return {"error": "An error has occrured."}, 500

    log("containers_actions", format="[{date}|IP:{ip}] Admin retrieved images : '{images}'", images=images)
    return {"images": images}

@containers_bp.route('/api/settings/update', methods=['POST'])
@admins_only
def route_update_settings():
    required_fields = [
        "docker_base_url", "docker_hostname", "container_expiration",
        "container_maxmemory", "container_maxcpu", "docker_assignment"
    ]

    for field in required_fields:
        if request.form.get(field) is None:
            return {"error": f"Missing required field: {field}"}, 400

    settings = {
        "docker_base_url": request.form.get("docker_base_url"),
        "docker_hostname": request.form.get("docker_hostname"),
        "container_expiration": request.form.get("container_expiration"),
        "container_maxmemory": request.form.get("container_maxmemory"),
        "container_maxcpu": request.form.get("container_maxcpu"),
        "docker_assignment": request.form.get("docker_assignment")
    }

    for key, value in settings.items():
        setting = ContainerSettingsModel.query.filter_by(key=key).first()
        if setting is None:
            # Create
            new_setting = ContainerSettingsModel(key=key, value=value)
            db.session.add(new_setting)
            log("containers_actions", format=f"[{{date}}|IP:{{ip}}] Admin created '{key}' setting DB row")
        else:
            # Update
            setting.value = value
            log("containers_actions", format="[{date}|IP:{ip}] Admin updated '{key}' setting DB row", key=key)

    db.session.commit()

    container_manager.settings = settings_to_dict(ContainerSettingsModel.query.all())

    if container_manager.settings.get("docker_base_url") is not None:
        try:
            container_manager.initialize_connection(container_manager.settings, current_app)
            log("containers_actions", format="[{date}|IP:{ip}] Admin successfully initialized connection to Docker daemon")
        except Exception as err:
            log("containers_errors",
                format="[{date}|IP:{ip}] Admin error initializing connection to Docker daemon ({error})",
                error=str(err))
            flash(str(err), "error")
            return redirect(url_for(".route_containers_settings"))

    return redirect(url_for(".route_containers_dashboard"))

from flask import current_app
import traceback

@containers_bp.route('/dashboard', methods=['GET'])
@admins_only
def route_containers_dashboard():
    try:
        running_containers = ContainerInfoModel.query.order_by(
            ContainerInfoModel.timestamp.desc()).all()

        connected = False
        try:
            connected = container_manager.is_connected()
        except Exception as err:
            log("containers_errors", format="[{date}|IP:{ip}] Error checking if Docker daemon is connected ({error})",
                    error=str(err))

        for i, container in enumerate(running_containers):
            try:
                running_containers[i].is_running = container_manager.is_container_running(
                    container.container_id)
            except Exception as err:
                log("containers_errors", format="[{date}|IP:{ip}] Error checking if container is running ({error})",
                        error=str(err))
                running_containers[i].is_running = False

        # Get the docker_assignment setting
        docker_assignment = container_manager.settings.get("docker_assignment")

        current_app.logger.info(f"Rendering dashboard with {len(running_containers)} containers and docker_assignment: {docker_assignment}")

        return render_template('container_dashboard.html', 
                               containers=running_containers, 
                               connected=connected, 
                               settings={'docker_assignment': docker_assignment})
    except Exception as err:
        log("containers_errors", format="[{date}|IP:{ip}] Error rendering container dashboard ({error})",
                error=str(err))
        return f"An error has occurred.", 500  # Return error message and 500 status code

@containers_bp.route('/settings', methods=['GET'])
@admins_only
def route_containers_settings():
    running_containers = ContainerInfoModel.query.order_by(
        ContainerInfoModel.timestamp.desc()).all()

    log("containers_actions", format="[{date}|IP:{ip}] Admin Container settings called")
    return render_template('container_settings.html', settings=container_manager.settings)
