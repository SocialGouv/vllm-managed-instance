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

instanceName = "ollama-managed-instance" + instanceNameSuffix
serviceName = getRequiredEnv("OVH_SERVICE_NAME")
sshKeyId = getRequiredEnv("OVH_SSH_KEY_ID")
flavorId = getRequiredEnv("OVH_INSTANCE_FLAVOR_ID")
imageId = getRequiredEnv("OVH_INSTANCE_IMAGE_ID")
region = getRequiredEnv("OVH_REGION")
authToken = getRequiredEnv("AUTH_TOKEN")
users = os.getenv("USERS", "")
modelName = getRequiredEnv("MODEL_NAME")
serviceReplicas = os.getenv("SERVICE_REPLICAS", "")
gpuByReplica = os.getenv("GPU_BY_REPLICA", "")

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
      if 'docker' not in user['groups']:
          user['groups'].append('docker')
  users = yaml.dump(parsedUsers)



f = open("templates/docker-compose.tpl", "r")
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
  
write_files:
  - path: /home/ubuntu/.ssh/id_ed25519
    permissions: "0600"
    owner: ubuntu:ubuntu
    content: |
  - path: /opt/ollama/init.sh
    owner: ubuntu:ubuntu
    permissions: "0775"
    content: |
        #!/bin/bash

        # init config
        sudo mkdir -p /opt/ollama
        sudo chown -R ubuntu:ubuntu /opt
        sudo chmod -R 0775 /opt

        cd /opt/ollama
        cat <<'EOF' > docker-compose.tpl
{dockerCompose}
        EOF
        
        # install gomplate
        mkdir -p ~/bin
        curl -L https://github.com/hairyhenderson/gomplate/releases/download/v3.9.0/gomplate_linux-amd64 -o ~/bin/gomplate
        chmod +x ~/bin/gomplate
        echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc
        source ~/.bashrc

        # generate docker compose
        export HOST_GPU_COUNT=$(nvidia-smi --query-gpu=name --format=csv,noheader | wc -l)
        export SERVICE_REPLICAS={serviceReplicas}
        if [ -z $SERVICE_REPLICAS ]; then
          export SERVICE_REPLICAS=$HOST_GPU_COUNT
        fi
        export GPU_BY_REPLICA={gpuByReplica}
        if [ -z $GPU_BY_REPLICA ]; then
          export GPU_BY_REPLICA=$HOST_GPU_COUNT
        fi
        cat docker-compose.tpl | gomplate -o docker-compose.yaml

        echo "TOKEN={authToken}" >> .env
        echo "HOST=$(curl -4 ifconfig.me)" >> .env
        echo "CREDENTIALS='$(htpasswd -nBb user {authToken})'" >> .env

        # Configure Docker to use Nvidia driver
        nvidia-ctk runtime configure --runtime=docker
        systemctl restart docker

        # up docker compose services
        docker compose up -d --build
        docker exec ollama-ollama-service-1-1 ollama run {modelName}
        touch /tmp/runcmd_finished

  - path: /etc/ssh/sshd_config.d/90-custom-settings.conf
    content: |
      AuthenticationMethods publickey
      AuthorizedKeysFile .ssh/authorized_keys
      PasswordAuthentication no
      PermitRootLogin no
      AllowGroups ubuntu

runcmd:
  - su - ubuntu -c '/opt/ollama/init.sh > /opt/ollama/init.log 2>&1'

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

elif action == "delete":
    instanceId = findInstance()
    if not instanceId:
        logger.error(f"Could not find instance with name {instanceName}")
        sys.exit(1)
    client.delete(f"/cloud/project/{serviceName}/instance/{instanceId}")
    logger.info("Deleted instance")
else:
    logger.error("Invalid action. Use 'create' or 'delete'.")
