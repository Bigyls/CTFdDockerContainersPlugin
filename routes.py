"""
This module defines the routes and blueprint for the containers plugin in CTFd.
It handles container management operations such as running, requesting, renewing,
resetting, stopping, and purging containers, as well as administrative functions
like updating settings and viewing the container dashboard.
"""

import datetime

from flask import Blueprint, request, Flask, render_template, url_for, redirect, current_app

from CTFd.models import db
from CTFd.utils.decorators import authed_only, admins_only, during_ctf_time_only, ratelimit, require_verified_emails
from CTFd.utils.user import get_current_user

# Import custom modules and helper functions for managing containers
from .logs import log
from .models import ContainerInfoModel, ContainerSettingsModel
from .container_manager import ContainerManager
from .container_challenge import ContainerChallenge
from .routes_helper import format_time_filter, create_container, renew_container, kill_container

# Blueprint definition for the containers module
containers_bp = Blueprint(
    'containers', __name__, template_folder='templates', static_folder='assets', url_prefix='/containers')

def settings_to_dict(settings):
    """
    Convert settings objects to a dictionary.

    Args:
        settings (list): A list of settings model objects.

    Returns:
        dict: A dictionary with setting keys and values.
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

    # Initialize a global container manager using the app context and settings
    app.container_manager = ContainerManager(container_settings, app)
    return containers_bp

def format_time_filter(timestamp):
    """
    Format a timestamp into a readable string.

    Args:
        timestamp (float): Unix timestamp.

    Returns:
        str: A human-readable formatted timestamp.
    """
    return datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

# Register the time formatting filter for templates
containers_bp.app_template_filter("format_time")(format_time_filter)

@containers_bp.route('/api/running', methods=['POST'])
@authed_only
@during_ctf_time_only
@require_verified_emails
@ratelimit(method="POST", limit=100, interval=300, key_prefix='rl_running_container_post')
def route_running_container():
    """
    Check if a container is running for a given challenge.

    This route verifies if a user already has an active container for a challenge
    based on the challenge ID (`chal_id`) sent in the request.

    Returns:
        dict: JSON response with the container status.
    """
    user = get_current_user()
    log("containers_debug", format="Checking running container status")

    # Validate the request parameters
    if request.json is None or request.json.get("chal_id") is None or user is None:
        log("containers_errors", format="Invalid request to /api/running")
        return {"error": "Invalid request"}, 400

    try:
        # Fetch challenge information
        challenge = ContainerChallenge.challenge_model.query.filter_by(id=request.json.get("chal_id")).first()
        if challenge is None:
            log("containers_errors", format="CHALL_ID:{challenge_id}|Challenge not found during running container check",
                challenge_id=request.json.get("chal_id"))
            return {"error": "An error occurred."}, 500

        docker_assignment = current_app.container_manager.settings.get("docker_assignment")
        log("containers_debug", format="CHALL_ID:{challenge_id}|Docker assignment mode: {mode}",
            challenge_id=challenge.id,
            mode=docker_assignment)

        # Determine container ownership based on assignment type
        if docker_assignment in ["user", "unlimited"]:
            running_container = ContainerInfoModel.query.filter_by(
                challenge_id=challenge.id,
                user_id=user.id).first()
        else:
            running_container = ContainerInfoModel.query.filter_by(
                challenge_id=challenge.id, team_id=user.team_id).first()

        # Return the status of the container (running or stopped)
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
        return {"error": "An error has occurred."}, 500

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
        docker_assignment = current_app.container_manager.settings.get("docker_assignment")
        log("containers_debug", format="CHALL_ID:{challenge_id}|Docker assignment mode: {mode}",
            challenge_id=request.json.get("chal_id"),
            mode=docker_assignment)

        return create_container(current_app.container_manager, request.json.get("chal_id"), user.id, user.team_id, docker_assignment)
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
        docker_assignment = current_app.container_manager.settings.get("docker_assignment")
        log("containers_debug", format="CHALL_ID:{challenge_id}|Docker assignment mode: {mode}",
            challenge_id=request.json.get("chal_id"),
            mode=docker_assignment)

        return renew_container(current_app.container_manager, request.json.get("chal_id"), user.id, user.team_id, docker_assignment)
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

    docker_assignment = current_app.container_manager.settings.get("docker_assignment")
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
        kill_container(current_app.container_manager, running_container.container_id, request.json.get("chal_id"))

    log("containers_actions", format="CHALL_ID:{challenge_id}|Recreating container",
        challenge_id=request.json.get("chal_id"))
    return create_container(current_app.container_manager, request.json.get("chal_id"), user.id, user.team_id, docker_assignment)

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

    docker_assignment = current_app.container_manager.settings.get("docker_assignment")
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
        return kill_container(current_app.container_manager, running_container.container_id, request.json.get("chal_id"))

    log("containers_errors", format="CHALL_ID:{challenge_id}|No running container found to stop",
        challenge_id=request.json.get("chal_id"))
    return {"error": "No running container found."}, 400

@containers_bp.route('/api/kill', methods=['POST'])
@admins_only
def route_kill_container():
    """
    Admin route to kill a specific container by its ID.
    """
    # Validate the request data to ensure a container ID is provided
    if request.json is None or request.json.get("container_id") is None:
        log("containers_errors", format="Invalid request to /api/kill")
        return {"error": "Invalid request"}, 400

    # Extract the container ID and perform the kill operation
    container_id = request.json.get("container_id")
    log("containers_actions", format="Admin killing container '{container_id}'", container_id=container_id)
    return kill_container(current_app.container_manager, container_id, "N/A")

@containers_bp.route('/api/purge', methods=['POST'])
@admins_only
def route_purge_containers():
    """
    Admin route to purge (stop and delete) all containers currently managed by the application.

    This endpoint allows administrators to kill all active containers at once. It should be used with caution,
    as it will affect all active users and their challenge sessions.
    """
    log("containers_actions", format="Requesting container purge")

    # Retrieve all containers stored in the database
    containers = ContainerInfoModel.query.all()

    # Loop through each container and attempt to stop/kill it
    for container in containers:
        try:
            log("containers_actions", format="Admin killing container '{container_id}'",
                container_id=container.container_id)
            # Attempt to kill the container using its ID
            kill_container(current_app.container_manager, container.container_id, "N/A")
        except Exception as err:
            # Log any errors encountered while killing individual containers
            log("containers_errors", format="Error during purging container '{container_id}' ({error})",
                container_id=container.container_id,
                error=str(err))

    # Log the successful completion of the purge operation
    log("containers_actions", format="Admin completed container purge")
    return {"success": "Purged all containers"}, 200

@containers_bp.route('/api/images', methods=['GET'])
@admins_only
def route_get_images():
    """
    Admin route to retrieve a list of all available Docker images.

    This endpoint provides administrators with a list of Docker images that are available for container creation.
    The list is fetched directly from the Docker registry managed by the container manager.
    """
    log("containers_debug", format="Admin requesting Docker images list")

    try:
        # Attempt to retrieve the list of available Docker images
        images = current_app.container_manager.get_images()
        # Log the number of images successfully retrieved
        log("containers_actions", format="Admin successfully retrieved {count} Docker images",
                count=len(images))

        # Return the list of images as a JSON response
        return {"images": images}, 200
    except Exception as err:
        # Log any errors encountered during the process of fetching Docker images
        log("containers_errors", format="Admin encountered error while fetching Docker images ({error})",
                error=str(err))
        return {"error": "An error has occurred."}, 500

@containers_bp.route('/api/settings/update', methods=['POST'])
@admins_only
def route_update_settings():
    """
    Admin route to update container settings.

    This route allows administrators to modify container-related configurations such as Docker base URL,
    hostname, expiration time, memory, and CPU settings. These settings are used by the container manager
    to handle container creation and management.
    """
    log("containers_debug", format="Admin initiating settings update")

    # Define the list of required fields that must be present in the request form
    required_fields = [
        "docker_base_url", "docker_hostname", "container_expiration",
        "container_maxmemory", "container_maxcpu", "docker_assignment"
    ]

    # Check if any required field is missing and log an error if found
    for field in required_fields:
        if request.form.get(field) is None:
            log("containers_errors", format="Admin settings update failed: Missing required field {field}",
                field=field)
            return {"error": f"Missing required field: {field}"}, 400

    # Retrieve the settings from the request and store them in a dictionary
    settings = {
        "docker_base_url": request.form.get("docker_base_url"),
        "docker_hostname": request.form.get("docker_hostname"),
        "container_expiration": request.form.get("container_expiration"),
        "container_maxmemory": request.form.get("container_maxmemory"),
        "container_maxcpu": request.form.get("container_maxcpu"),
        "docker_assignment": request.form.get("docker_assignment")
    }

    try:
        # Update or create each setting in the database
        for key, value in settings.items():
            setting = ContainerSettingsModel.query.filter_by(key=key).first()
            if setting is None:
                # Create a new setting if it doesn't exist in the database
                new_setting = ContainerSettingsModel(key=key, value=value)
                db.session.add(new_setting)
                log("containers_actions", format=f"Admin created '{key}' setting DB row")
            else:
                # Update the setting if it already exists and log the change
                old_value = setting.value
                if old_value != value:
                    setting.value = value
                    log("containers_actions", format="Admin updated '{key}' setting DB row ({old_value} => {new_value})",
                        key=key, old_value=old_value, new_value=value)
    except Exception as err:
        # Log any errors encountered during the update operation
        log("containers_errors", format="Admin encountered error while updating settings ({error})",
            error=str(err))
        return {"error": "An error has occurred."}, 500

    try:
        # Commit the changes to the database
        db.session.commit()
        log("containers_actions", format="Admin successfully committed settings to database")
    except Exception as err:
        # If there's an error during commit, roll back the transaction and log the issue
        db.session.rollback()
        log("containers_errors", format="Admin encountered error while committing settings ({error})",
            error=str(err))
        return {"error": "Failed to update settings in database"}, 500

    try:
        # Reload settings into the container manager to apply changes immediately
        all_settings = ContainerSettingsModel.query.all()
        new_settings = settings_to_dict(all_settings)
        with current_app.app_context():
                    current_app.container_manager.settings.update(new_settings)
        log("containers_actions", format="Admin completed settings update. New settings: {settings}",
                settings=current_app.container_manager.settings)
    except Exception as err:
        # Log any error that occurs while updating the container manager settings
        log("containers_errors", format="Admin encountered error while updating container_manager settings ({error})",
            error=str(err))
        return {"error": "Failed to update container manager settings"}, 500

    # Redirect to the containers dashboard after successfully updating the settings
    return redirect(url_for(".route_containers_dashboard"))

@containers_bp.route('/dashboard', methods=['GET'])
@admins_only
def route_containers_dashboard():
    """
    Admin route to view the containers dashboard.

    This route provides an overview of all running containers, their status, and whether the Docker daemon
    is currently connected. It allows administrators to view and manage active containers.
    """
    admin_user = get_current_user()
    log("containers_actions", format="Admin accessing container dashboard", user_id=admin_user.id)

    try:
        # Retrieve all running containers from the database, ordered by timestamp
        running_containers = ContainerInfoModel.query.order_by(
            ContainerInfoModel.timestamp.desc()).all()
        log("containers_debug", format="Admin retrieved {count} containers from database",
            user_id=admin_user.id, count=len(running_containers))

        # Check if the Docker daemon is connected
        connected = False
        try:
            connected = current_app.container_manager.is_connected()
            log("containers_debug", format="Admin checked Docker daemon connection: {status}",
                user_id=admin_user.id, status="Connected" if connected else "Disconnected")
        except Exception as err:
            # Log any errors encountered during Docker connection check
            log("containers_errors", format="Admin encountered error checking Docker daemon connection: {error}",
                user_id=admin_user.id, error=str(err))

        # Check the running status of each container and update the corresponding field
        for i, container in enumerate(running_containers):
            try:
                running_containers[i].is_running = current_app.container_manager.is_container_running(
                    container.container_id)
                log("containers_debug", format="Admin checked container '{container_id}' status: {status}",
                    user_id=admin_user.id, container_id=container.container_id,
                    status="Running" if running_containers[i].is_running else "Stopped")
            except Exception as err:
                # Log any errors encountered while checking container status
                log("containers_errors", format="Admin encountered error checking container '{container_id}' status: {error}",
                    user_id=admin_user.id, container_id=container.container_id, error=str(err))
                running_containers[i].is_running = False

        # Retrieve the current Docker assignment mode from settings
        docker_assignment = current_app.container_manager.settings.get("docker_assignment")
        log("containers_debug", format="Admin retrieved Docker assignment mode: {mode}",
            user_id=admin_user.id, mode=docker_assignment)

        # Render the dashboard template with the necessary context data
        log("containers_debug", format="Admin rendering dashboard with {running_containers} containers and docker_assignment to {docker_assignment}",
            user_id=admin_user.id, running_containers=len(running_containers),
            docker_assignment=docker_assignment)

        return render_template('container_dashboard.html',
                               containers=running_containers,
                               connected=connected,
                               settings={'docker_assignment': docker_assignment})
    except Exception as err:
        # Log any errors that occur while loading or rendering the dashboard
        log("containers_errors", format="Admin encountered error rendering container dashboard: {error}",
            user_id=admin_user.id, error=str(err))
        current_app.logger.error(f"Error in container dashboard: {str(err)}", exc_info=True)
        return "An error occurred while loading the dashboard. Please check the logs.", 500

@containers_bp.route('/settings', methods=['GET'])
@admins_only
def route_containers_settings():
    """
    Admin route to view and edit container settings.

    This route displays the current container-related settings and allows administrators to modify them.
    It serves as an interface for managing configurations used by the container manager.
    """
    # Retrieve the list of running containers and current settings from the database
    running_containers = ContainerInfoModel.query.order_by(
        ContainerInfoModel.timestamp.desc()).all()
    log("containers_actions", format="Admin Container settings called")

    # Render the settings template with the retrieved settings and containers
    return render_template('container_settings.html', settings=current_app.container_manager.settings)
