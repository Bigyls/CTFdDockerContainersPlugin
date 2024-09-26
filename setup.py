from CTFd.utils import set_config

def setup_default_configs():
    for key, val in {
        'docker_base_url': 'unix:///var/run/docker.sock',
        'docker_hostname': '',
        'container_expiration': '45',
        'container_maxmemory': '512',
        'container_maxcpu': '0.5',
        'docker_assignment': 'user',
    }.items():
        set_config('container_settings_model:' + key, val)
