from CTFd.utils import set_config
from .models import db

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
        set_config(f"containers:{key}", val)

    db.session.commit()
