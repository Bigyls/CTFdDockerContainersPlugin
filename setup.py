from .models import db, ContainerSettingsModel

def setup_default_configs():
    """
    Sets up default configurations for container settings in the database.

    This function initializes the essential container settings required for the system to function properly.
    If any of these settings are not yet defined in the database, it applies the default values specified
    in the function. Once all settings are verified or updated, the changes are committed to the database.
    """
    # Dictionary containing the default configuration values
    default_configs = {
        "setup": "true",                                  # Indicates whether initial setup is completed
        "docker_base_url": "unix://var/run/docker.sock",  # URL for connecting to the Docker daemon
        "docker_hostname": "",                            # Hostname of the Docker server (empty by default)
        "container_expiration": "45",                     # Default expiration time for containers (in minutes)
        "container_maxmemory": "512",                     # Maximum memory limit for containers (in MB)
        "container_maxcpu": "0.5",                        # Maximum CPU allocation for containers
        "docker_assignment": "user",                      # Assignment mode for Docker containers (e.g., 'user', 'team' or 'unlimited')
    }

    # Iterate over each key-value pair in the default configurations
    for key, val in default_configs.items():
        # Check if the configuration already exists, and if not, apply the default value
        ContainerSettingsModel.apply_default_config(key, val)

    # Commit the changes to the database to ensure the new settings are saved
    db.session.commit()
