import os
import sys
import time
import logging
import requests
import yaml

import ovh
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, stream=sys.stderr)


def getRequiredEnv(key):
    value = os.getenv(key)
    if not value:
        logger.error(f"Env var {key} required but not defined")
        sys.exit(1)
    return value

def indentString(input_string, indent_level=4):
    indent = ' ' * indent_level
    return '\n'.join(indent + line for line in input_string.splitlines())

if len(sys.argv) != 2:
    logger.error("Usage: python script.py <create|delete>")
    sys.exit(1)

action = sys.argv[1].lower()
load_dotenv()

client = ovh.Client(
    endpoint=getRequiredEnv("OVH_ENDPOINT"),
    application_key=getRequiredEnv("OVH_APPLICATION_KEY"),
    application_secret=getRequiredEnv("OVH_APPLICATION_SECRET"),
    consumer_key=getRequiredEnv("OVH_CONSUMER_KEY"),
)

instanceNameSuffix = os.getenv("INSTANCE_NAME_SUFFIX", "")
if (instanceNameSuffix):
    instanceNameSuffix = f"-{instanceNameSuffix}"

instanceName = "vllm-managed-instance" + instanceNameSuffix
serviceName = getRequiredEnv("OVH_SERVICE_NAME")
sshKeyId = getRequiredEnv("OVH_SSH_KEY_ID")
flavorId = getRequiredEnv("OVH_INSTANCE_FLAVOR_ID")
imageId = getRequiredEnv("OVH_INSTANCE_IMAGE_ID")
region = getRequiredEnv("OVH_REGION")
authToken = getRequiredEnv("AUTH_TOKEN")
huggingFaceHubToken = os.getenv("HUGGING_FACE_HUB_TOKEN")
model = os.getenv("MODEL", "")
users = os.getenv("USERS", "")
gitPrivateDeployKey = os.getenv("GIT_PRIVATE_DEPLOY_KEY", "")
pythonVersion = os.getenv("PYTHON_VERSION", "3.11")
gitRepo = os.getenv("GIT_REPO", "")

gitPrivateDeployKey = indentString(gitPrivateDeployKey, 8)

if users:
  users = f"""
users:
{users}
"""
  parsedUsers = yaml.safe_load(users)
  for user in parsedUsers['users']:
    if 'name' in user:
      if 'primary_group' not in user:
          user['primary_group'] = user['name']
      if 'groups' not in user:
          user['groups'] = []
      if user['primary_group'] not in user['groups']:
          user['groups'].append(user['primary_group'])
      if 'sshusers' not in user['groups']:
          user['groups'].append('sshusers')
      if 'docker' not in user['groups']:
          user['groups'].append('docker')
  users = yaml.dump(parsedUsers)



f = open("docker-compose.yaml", "r")
dockerCompose = indentString(f.read(), 8)

userData = f"""
#cloud-config

ssh_pwauth: false

packages:
  # creds
  - apache2-utils
  - pwgen
  
  # debug
  - micro
  - bpytop
  
  # scripting
  - jq
  
  # python pyenv deps
  - make
  - build-essential
  - libssl-dev
  - zlib1g-dev
  - libbz2-dev
  - libreadline-dev
  - libsqlite3-dev
  - wget
  - curl
  - llvm
  - libncurses5-dev
  - libncursesw5-dev
  - xz-utils
  - tk-dev
  - libffi-dev
  - liblzma-dev
  - python3-openssl

write_files:
  - path: /etc/profile.d/pyenv.sh
    permissions: "0444"
    owner: root:root
    content: |
        #!/bin/bash
        export PYENV_ROOT="$HOME/.pyenv"
        export PATH="$PYENV_ROOT/bin:$PATH"

        # Check if pyenv is not installed
        if ! command -v pyenv 1>/dev/null 2>&1; then
            curl https://pyenv.run | bash
            # Reload the shell to recognize pyenv
            export PATH="$PYENV_ROOT/bin:$PATH"
            eval "$(pyenv init --path)"
            eval "$(pyenv init -)"
            
            PYTHON_VERSION="{pythonVersion}"
            pyenv install $PYTHON_VERSION
            pyenv global $PYTHON_VERSION
            
            # Install Poetry
            curl -sSL https://install.python-poetry.org | python3 -
            
            # Set Poetry to use the pyenv Python version
            poetry env use $(pyenv which python)
        fi

        eval "$(pyenv init --path)"
        eval "$(pyenv init -)"


  - path: /home/ubuntu/.ssh/id_ed25519
    permissions: "0600"
    owner: ubuntu:ubuntu
    content: |
{gitPrivateDeployKey}
  - path: /opt/vllm/init.sh
    owner: ubuntu:ubuntu
    permissions: "0775"
    content: |
        #!/bin/bash

        set -Eeuo pipefail

        if ! getent group "sshusers" > /dev/null 2>&1; then
          sudo groupadd sshusers
        fi
        sudo usermod -a -G sshusers ubuntu # ubuntu groups seem to be overided

        # init config
        sudo mkdir -p /opt/vllm
        sudo chown -R ubuntu:sshusers /opt
        sudo chmod -R 0775 /opt

        cd /opt/vllm
        cat <<'EOF' > docker-compose.yaml
{dockerCompose}
        EOF
        echo "TOKEN={authToken}" >> .env
        echo "HOST=$(curl -4 ifconfig.me)" >> .env
        echo "CREDENTIALS='$(htpasswd -nBb user {authToken})'" >> .env
        echo "HUGGING_FACE_HUB_TOKEN='{huggingFaceHubToken}'" >> .env
        echo "MODEL='{model}'" >> .env
        
        # up docker compose services
        docker compose up -d --build
        touch /tmp/runcmd_finished

        # clone working git repo
        cd /opt/vllm
        if [ -n "{gitRepo}" ]; then
            ssh-keyscan -H github.com >> ~/.ssh/known_hosts
            sudo su - ubuntu -c "git clone {gitRepo}"
        fi
  - path: /etc/ssh/sshd_config.d/90-custom-settings.conf
    content: |
      AuthenticationMethods publickey
      AuthorizedKeysFile .ssh/authorized_keys
      PasswordAuthentication no
      PermitRootLogin no
      AllowGroups sshusers

runcmd:
  - su - ubuntu -c '/opt/vllm/init.sh > /var/log/vllm-init.log 2>&1'

groups:
  - name: sshusers

{users}
"""

# debug
# print(userData)
# sys.exit(0)

def findInstance():
    instances = client.get(f"/cloud/project/{serviceName}/instance")
    if not instances:
        logger.error("Could not get available instances")
        sys.exit(1)
    for instance in instances:
        if not instance["name"] == instanceName:
            continue
        return instance["id"]
    return None


def findIpInInstance(response):
    if not response or "ipAddresses" not in response or not response["ipAddresses"]:
        logger.error("Error looking for IPv4 in API response", response)
        return None
    for ip in response["ipAddresses"]:
        if (
            ip
            and "version" in ip
            and ip["version"] == 4
            and "type" in ip
            and ip["type"] == "public"
            and "ip" in ip
            and ip["ip"]
        ):
            return ip["ip"]
    logger.error("Error looking for IPv4 in API response", response)
    return None


def findStatusInInstance(response):
    if not response or "status" not in response or not response["status"]:
        logger.error("Error looking for status in API response", response)
        return None
    return response["status"]


if action == "create":
    if findInstance():
        logger.error(f"Instance with name {instanceName} already exists")
        sys.exit(1)
    createResponse = client.post(
        f"/cloud/project/{serviceName}/instance",
        name=instanceName,
        sshKeyId=sshKeyId,
        imageId=imageId,
        flavorId=flavorId,
        region=region,
        userData=userData,
    )
    if not createResponse or "id" not in createResponse:
        logger.error("Error creating instance", createResponse)
        sys.exit(1)
    else:
        logger.info("Created instance", createResponse)

    # waiting for instance to be ready
    instanceResponse = client.get(
        f"/cloud/project/{serviceName}/instance/{createResponse['id']}"
    )
    while findStatusInInstance(instanceResponse) == "BUILD":
        logger.info("Instance is building...")
        instanceResponse = client.get(
            f"/cloud/project/{serviceName}/instance/{createResponse['id']}"
        )
        time.sleep(3)

    if findStatusInInstance(instanceResponse) != "ACTIVE":
        logger.error(
            "Error creating instance on OVH, status:",
            findStatusInInstance(instanceResponse),
        )
        sys.exit(1)

    logger.info("Instance is ready")
    ip = findIpInInstance(instanceResponse)
    if not ip:
        logger.error("Error finding IP in instance response")
        sys.exit(1)
    logger.info(f"Instance domain: {ip}.nip.io")

    # url = f"https://{ip}.nip.io/v1/models"
    # max_attempts = 120
    # wait_time = 5
    # attempt = 1
    # while attempt <= max_attempts:
    #     try:
    #         response = requests.get(url)
    #         if response.status_code == 401:
    #             logger.info(f"URL {url} is ready.")
    #             break
    #     except requests.ConnectionError:
    #         pass
    #     logger.info(f"Attempt {attempt}/{max_attempts}: URL not ready (HTTP status code: {response.status_code if 'response' in locals() else 'Connection error'}). Waiting {wait_time} seconds...")
    #     time.sleep(wait_time)
    #     attempt += 1
    # else:
    #     logger.info("URL is not ready after maximum attempts.")
    #     sys.exit(1)



elif action == "delete":
    instanceId = findInstance()
    if not instanceId:
        logger.error(f"Could not find instance with name {instanceName}")
        sys.exit(1)
    client.delete(f"/cloud/project/{serviceName}/instance/{instanceId}")
    logger.info("Deleted instance")
else:
    logger.error("Invalid action. Use 'create' or 'delete'.")
