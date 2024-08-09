import os
import sys
import time
import logging
import requests

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

instanceName = "vllm-managed-instance"
serviceName = getRequiredEnv("OVH_SERVICE_NAME")
sshKeyId = getRequiredEnv("OVH_SSH_KEY_ID")
flavorId = getRequiredEnv("OVH_INSTANCE_FLAVOR_ID")
imageId = getRequiredEnv("OVH_INSTANCE_IMAGE_ID")
region = getRequiredEnv("OVH_REGION")
authToken = getRequiredEnv("AUTH_TOKEN")
huggingFaceHubToken = os.getenv("HUGGING_FACE_HUB_TOKEN")
model = os.getenv("MODEL")

f = open("docker-compose.yaml", "r")
dockerCompose = indentString(f.read(), 8)

userData = f"""
#cloud-config

packages:
  - apache2-utils
  - pwgen
  - micro

write_files:
  - path: /home/ubuntu/init.sh
    permissions: "0755"
    content: |
        #!/bin/bash 

        set -Eeuo pipefail
        cd /home/ubuntu
        cat <<'EOF' > docker-compose.yaml
{dockerCompose}
        EOF
        echo "HOST=$(curl -4 ifconfig.me)" >> .env
        echo "CREDENTIALS='$(htpasswd -nBb user {authToken})'" >> .env
        echo "HUGGING_FACE_HUB_TOKEN='{huggingFaceHubToken}'" >> .env
        echo "MODEL='{model}'" >> .env
        docker compose up -d --build
        touch /tmp/runcmd_finished

runcmd:
  - su - ubuntu -c '/home/ubuntu/init.sh > init.log 2>&1'
"""

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

    url = f"https://{ip}.nip.io/v1/models"
    max_attempts = 120
    wait_time = 5
    attempt = 1
    while attempt <= max_attempts:
        try:
            response = requests.get(url)
            if response.status_code == 401:
                logger.info(f"URL {url} is ready.")
                break
        except requests.ConnectionError:
            # If there's a connection error, ignore and try again
            pass

        # If the response code is not 200, wait and try again
        logger.info(f"Attempt {attempt}/{max_attempts}: URL not ready (HTTP status code: {response.status_code if 'response' in locals() else 'Connection error'}). Waiting {wait_time} seconds...")
        time.sleep(wait_time)
        attempt += 1
    else:
        logger.info("URL is not ready after maximum attempts.")
        sys.exit(1)



elif action == "delete":
    instanceId = findInstance()
    if not instanceId:
        logger.error(f"Could not find instance with name {instanceName}")
        sys.exit(1)
    client.delete(f"/cloud/project/{serviceName}/instance/{instanceId}")
    logger.info("Deleted instance")
else:
    logger.error("Invalid action. Use 'create' or 'delete'.")
