from .models import db, ContainerSettingsModel

def setup_default_configs():
    for key, val in {
        "setup": "true",
        "docker_base_url": "unix://var/run/docker.sock",
        "docker_hostname": "",
        "container_expiration": "45",
        "container_maxmemory": "512",
        "container_maxcpu": "0.5",
        "docker_assignment": "user",
    }.items():
        ContainerSettingsModel.apply_default_config(key, val)

    db.session.commit()
