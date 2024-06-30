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

def settings_to_dict(settings):
    return {
        setting.key: setting.value for setting in settings
    }

containers_bp = Blueprint(
    'containers', __name__, template_folder='templates', static_folder='assets', url_prefix='/containers')
containers_bp.app_template_filter("format_time")(format_time_filter)  # Register the filter

def register_app(app: Flask):
    container_settings = settings_to_dict(ContainerSettingsModel.query.all())
    global container_manager
    container_manager = ContainerManager(container_settings, app)
    app.register_blueprint(containers_bp)

@containers_bp.route('/api/running', methods=['POST'])
@authed_only
@during_ctf_time_only
@require_verified_emails
# Rate limit to 100 requests per minute (be careful with this feature when event is on same network. Based on IP address, it will block all users on the same network.)
# @ratelimit(method="POST", limit=100, interval=60, key_prefix='rl_running_container_post')
def route_running_container():
    user = get_current_user()

    # Validate the request
    if request.json is None:
        return {"error": "Invalid request"}, 400

    if request.json.get("chal_id", None) is None:
        return {"error": "No chal_id specified"}, 400

    if user is None:
        return {"error": "User not found"}, 400

    try:
        challenge = ContainerChallenge.challenge_model.query.filter_by(
        id=request.json.get("chal_id")).first()

        # Make sure the challenge exists and is a container challenge
        if challenge is None:
            log("containers", format="[{date}|IP:{ip}|USER:{user_id}|CHALL:{challenge_id}] Challenge not found during checking if container is running",
                            user_id=user.id,
                            challenge_id=challenge)
            return {"error": "Challenge not found"}, 400

        # Check for any existing containers for the user
        running_containers = ContainerInfoModel.query.filter_by(
            challenge_id=challenge.id, user_id=user.team_id if user.team_id != None else user.id)
        running_container = running_containers.first()

        if running_container:
            return {"status": "already_running", "container_id": request.json.get("chal_id")}, 200

        else:
            return {"status": "stopped", "container_id": request.json.get("chal_id")}, 200

    except Exception as err:
        log("containers", format="[{date}|IP:{ip}|USER:{user_id}|CHALL:{challenge_id}] Error checking if container is running ({error})",
                        user_id=user.id,
                        challenge_id=request.json.get("chal_id"),
                        error=str(err))
        return {"error": str(err)}, 500

@containers_bp.route('/api/request', methods=['POST'])
@authed_only
@during_ctf_time_only
@require_verified_emails
# Rate limit to 100 requests per minute (be careful with this feature when event is on same network. Based on IP address, it will block all users on the same network.)
# @ratelimit(method="POST", limit=100, interval=60, key_prefix='rl_request_container_post')
def route_request_container():
    user = get_current_user()

    # Validate the request
    if request.json is None:
        return {"error": "Invalid request"}, 400

    if request.json.get("chal_id", None) is None:
        return {"error": "No chal_id specified"}, 400

    if user is None:
        return {"error": "User not found"}, 400

    try:
        log("containers", format="[{date}|IP:{ip}|USER:{user_id}|CHALL:{challenge_id}] Creating container",
                        user_id=user.id,
                        challenge_id=request.json.get("chal_id"))
        return create_container(container_manager, request.json.get("chal_id"), user.team_id if user.team_id != None else user.id)
    except ContainerException as err:
        log("containers", format="[{date}|IP:{ip}|USER:{user_id}|CHALL:{challenge_id}] Error creating container ({error})",
                        user_id=user.id,
                        challenge_id=request.json.get("chal_id"),
                        error=str(err))
        return {"error": str(err)}, 500

@containers_bp.route('/api/renew', methods=['POST'])
@authed_only
@during_ctf_time_only
@require_verified_emails
# Rate limit to 100 requests per minute (be careful with this feature when event is on same network. Based on IP address, it will block all users on the same network.)
# @ratelimit(method="POST", limit=100, interval=60, key_prefix='rl_renew_container_post')
def route_renew_container():
    user = get_current_user()

    # Validate the request
    if request.json is None:
        return {"error": "Invalid request"}, 400

    if request.json.get("chal_id", None) is None:
        return {"error": "No chal_id specified"}, 400

    if user is None:
        return {"error": "User not found"}, 400

    try:
        log("containers", format="[{date}|IP:{ip}|USER:{user_id}|CHALL:{challenge_id}] Renewing container",
                        user_id=user.id,
                        challenge_id=request.json.get("chal_id"))
        return renew_container(container_manager, request.json.get("chal_id"), user.team_id if user.team_id != None else user.id)
    except ContainerException as err:
        log("containers", format="[{date}|IP:{ip}|USER:{user_id}|CHALL:{challenge_id}] Error renewing container ({error})",
                        user_id=user.id,
                        challenge_id=request.json.get("chal_id"),
                        error=str(err))
        return {"error": str(err)}, 500

@containers_bp.route('/api/reset', methods=['POST'])
@authed_only
@during_ctf_time_only
@require_verified_emails
# Rate limit to 100 requests per minute (be careful with this feature when event is on same network. Based on IP address, it will block all users on the same network.)
# @ratelimit(method="POST", limit=100, interval=60, key_prefix='rl_restart_container_post')
def route_restart_container():
    user = get_current_user()

    # Validate the request
    if request.json is None:
        return {"error": "Invalid request"}, 400

    if request.json.get("chal_id", None) is None:
        return {"error": "No chal_id specified"}, 400

    if user is None:
        return {"error": "User not found"}, 400

    running_container: ContainerInfoModel = ContainerInfoModel.query.filter_by(
        challenge_id=request.json.get("chal_id"), user_id=user.team_id if user.team_id != None else user.id).first()

    if running_container:
        log("containers", format="[{date}|IP:{ip}|USER:{user_id}|CHALL:{challenge_id}] Reseting container",
                        user_id=user.id,
                        challenge_id=request.json.get("chal_id"))
        kill_container(container_manager, running_container.container_id)

    log("containers", format="[{date}|IP:{ip}|USER:{user_id}|CHALL:{challenge_id}] Recreating container",
                    user_id=user.id,
                    challenge_id=request.json.get("chal_id"))
    return create_container(container_manager, request.json.get("chal_id"), user.team_id if user.team_id != None else user.id)

@containers_bp.route('/api/stop', methods=['POST'])
@authed_only
@during_ctf_time_only
@require_verified_emails
# Rate limit to 100 requests per minute (be careful with this feature when event is on same network. Based on IP address, it will block all users on the same network.)
# @ratelimit(method="POST", limit=100, interval=60, key_prefix='rl_stop_container_post')
def route_stop_container():
    user = get_current_user()
    # Validate the request
    if request.json is None:
        return {"error": "Invalid request"}, 400

    if request.json.get("chal_id", None) is None:
        return {"error": "No chal_id specified"}, 400

    if user is None:
        return {"error": "User not found"}, 400

    running_container: ContainerInfoModel = ContainerInfoModel.query.filter_by(
        challenge_id=request.json.get("chal_id"), user_id=user.team_id if user.team_id != None else user.id).first()

    if running_container:
        log("containers", format="[{date}|IP:{ip}|USER:{user_id}|CHALL:{challenge_id}] Stoping container",
                        user_id=user.id,
                        challenge_id=request.json.get("chal_id"))
        return kill_container(container_manager, running_container.container_id)
    return {"error": "No container found"}, 400

@containers_bp.route('/api/kill', methods=['POST'])
@admins_only
def route_kill_container(container_manager, ):
    if request.json is None:
        return {"error": "Invalid request"}, 400

    if request.json.get("container_id", None) is None:
        return {"error": "No container_id specified"}, 400

    log("containers", format="[{date}|IP:{ip}] Admin killing container",
                    challenge_id=request.json.get("chal_id"))
    return kill_container(container_manager, request.json.get("container_id"))

@containers_bp.route('/api/purge', methods=['POST'])
@admins_only
def route_purge_containers():
    containers: "list[ContainerInfoModel]" = ContainerInfoModel.query.all()
    for container in containers:
        try:
            kill_container(container_manager, container.container_id)
        except ContainerException:
            pass
    log("containers", format="[{date}|IP:{ip}] Admin purged all containers")
    return {"success": "Purged all containers"}, 200

@containers_bp.route('/api/images', methods=['GET'])
@admins_only
def route_get_images():
    try:
        images = container_manager.get_images()
    except ContainerException as err:
        return {"error": str(err)}

    log("containers", format="[{date}|IP:{ip}] Admin retrieved images : '{images}'", images=images)
    return {"images": images}

@containers_bp.route('/api/settings/update', methods=['POST'])
@admins_only
def route_update_settings():
    if request.form.get("docker_base_url") is None:
        return {"error": "Invalid request"}, 400

    if request.form.get("docker_hostname") is None:
        return {"error": "Invalid request"}, 400

    if request.form.get("container_expiration") is None:
        return {"error": "Invalid request"}, 400

    if request.form.get("container_maxmemory") is None:
        return {"error": "Invalid request"}, 400

    if request.form.get("container_maxcpu") is None:
        return {"error": "Invalid request"}, 400

    docker_base_url = ContainerSettingsModel.query.filter_by(
        key="docker_base_url").first()

    docker_hostname = ContainerSettingsModel.query.filter_by(
        key="docker_hostname").first()

    container_expiration = ContainerSettingsModel.query.filter_by(
        key="container_expiration").first()

    container_maxmemory = ContainerSettingsModel.query.filter_by(
        key="container_maxmemory").first()

    container_maxcpu = ContainerSettingsModel.query.filter_by(
        key="container_maxcpu").first()

    # Create or update
    if docker_base_url is None:
        # Create
        docker_base_url = ContainerSettingsModel(
            key="docker_base_url", value=request.form.get("docker_base_url"))
        db.session.add(docker_base_url)
        log("containers", format="[{date}|IP:{ip}] Admin created 'docker_base_url' setting DB row")
    else:
        # Update
        docker_base_url.value = request.form.get("docker_base_url")
        log("containers", format="[{date}|IP:{ip}] Admin updated 'docker_base_url' setting DB row")

    # Create or update
    if docker_hostname is None:
        # Create
        docker_hostname = ContainerSettingsModel(
            key="docker_hostname", value=request.form.get("docker_hostname"))
        db.session.add(docker_hostname)
        log("containers", format="[{date}|IP:{ip}] Admin created 'docker_hostname' setting DB row")
    else:
        # Update
        docker_hostname.value = request.form.get("docker_hostname")
        log("containers", format="[{date}|IP:{ip}] Admin updated 'docker_hostname' setting DB row")

    # Create or update
    if container_expiration is None:
        # Create
        container_expiration = ContainerSettingsModel(
            key="container_expiration", value=request.form.get("container_expiration"))
        db.session.add(container_expiration)
        log("containers", format="[{date}|IP:{ip}] Admin created 'container_expiration' setting DB row")
    else:
        # Update
        container_expiration.value = request.form.get(
            "container_expiration")
        log("containers", format="[{date}|IP:{ip}] Admin updated 'container_expiration' setting DB row")

    # Create or update
    if container_maxmemory is None:
        # Create
        container_maxmemory = ContainerSettingsModel(
            key="container_maxmemory", value=request.form.get("container_maxmemory"))
        db.session.add(container_maxmemory)
        log("containers", format="[{date}|IP:{ip}] Admin created 'container_maxmemory' setting DB row")
    else:
        # Update
        container_maxmemory.value = request.form.get("container_maxmemory")
        log("containers", format="[{date}|IP:{ip}] Admin updated 'container_maxmemory' setting DB row")

    # Create or update
    if container_maxcpu is None:
        # Create
        container_maxcpu = ContainerSettingsModel(
            key="container_maxcpu", value=request.form.get("container_maxcpu"))
        db.session.add(container_maxcpu)
        log("containers", format="[{date}|IP:{ip}] Admin created 'container_maxcpu' setting DB row")
    else:
        # Update
        container_maxcpu.value = request.form.get("container_maxcpu")
        log("containers", format="[{date}|IP:{ip}] Admin updated 'container_maxcpu' setting DB row")

    db.session.commit()

    container_manager.settings = settings_to_dict(
        ContainerSettingsModel.query.all())

    if container_manager.settings.get("docker_base_url") is not None:
        try:
            container_manager.initialize_connection(
                container_manager.settings, current_app)
            log("containers", format="[{date}|IP:{ip}] Admin successfully initialized connection to Docker daemon")
        except ContainerException as err:
            log("containers", format="[{date}|IP:{ip}] Admin error initializing connection to Docker daemon ({error})", error=str(err))
            flash(str(err), "error")
            return redirect(url_for(".route_containers_settings"))

    return redirect(url_for(".route_containers_dashboard"))

@containers_bp.route('/dashboard', methods=['GET'])
@admins_only
def route_containers_dashboard():
    running_containers = ContainerInfoModel.query.order_by(
        ContainerInfoModel.timestamp.desc()).all()

    connected = False
    try:
        connected = container_manager.is_connected()
    except ContainerException:
        pass

    for i, container in enumerate(running_containers):
        try:
            running_containers[i].is_running = container_manager.is_container_running(
                container.container_id)
        except ContainerException:
            running_containers[i].is_running = False

    log("containers", format="[{date}|IP:{ip}] Admin Container dashboard called")
    return render_template('container_dashboard.html', containers=running_containers, connected=connected)

@containers_bp.route('/settings', methods=['GET'])
@admins_only
def route_containers_settings():
    running_containers = ContainerInfoModel.query.order_by(
        ContainerInfoModel.timestamp.desc()).all()

    log("containers", format="[{date}|IP:{ip}] Admin Container settings called")
    return render_template('container_settings.html', settings=container_manager.settings)
