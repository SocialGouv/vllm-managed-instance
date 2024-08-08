import ovh
import os
import sys
import time
from dotenv import load_dotenv


def getRequiredEnv(key):
    value = os.getenv(key)
    if not value:
        print(f"Env var {key} required but not defined")
        sys.exit(1)
    return value


if len(sys.argv) != 2:
    print("Usage: python script.py <create|delete>")
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
        curl -O https://raw.githubusercontent.com/SocialGouv/vllm-managed-instance/main/docker-compose.yaml
        echo "HOST=$(curl -4 ifconfig.me)" >> .env
        echo "CREDENTIALS='$(htpasswd -nBb user {authToken})'" >> .env
        docker compose up -d --build
        touch /tmp/runcmd_finished

runcmd:
  - su - ubuntu -c '/home/ubuntu/init.sh > init.log 2>&1'
"""


def findInstance():
    instances = client.get(f"/cloud/project/{serviceName}/instance")
    if not instances:
        print("Could not get available instances")
        sys.exit(1)
    for instance in instances:
        if not instance["name"] == instanceName:
            continue
        return instance["id"]
    return None


def findIpInInstance(response):
    if not response or "ipAddresses" not in response or not response["ipAddresses"]:
        print("Error looking for IPv4 in API response", response)
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
    print("Error looking for IPv4 in API response", response)
    return None


def findStatusInInstance(response):
    if not response or "status" not in response or not response["status"]:
        print("Error looking for status in API response", response)
        return None
    return response["status"]


if action == "create":
    if findInstance():
        print(f"Instance with name {instanceName} already exists")
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
        print("Error creating instance", createResponse)
        sys.exit(1)
    else:
        print("Created instance", createResponse)

    # waiting for instance to be ready
    instanceResponse = client.get(
        f"/cloud/project/{serviceName}/instance/{createResponse['id']}"
    )
    while findStatusInInstance(instanceResponse) == "BUILD":
        print("Instance is building...")
        instanceResponse = client.get(
            f"/cloud/project/{serviceName}/instance/{createResponse['id']}"
        )
        time.sleep(3)

    if findStatusInInstance(instanceResponse) != "ACTIVE":
        print(
            "Error creating instance on OVH, status:",
            findStatusInInstance(instanceResponse),
        )
        sys.exit(1)

    print("Instance is ready")
    ip = findIpInInstance(instanceResponse)
    if not ip:
        print("Error finding IP in instance response")
        sys.exit(1)
    print(f"Instance domain: {ip}.nip.io")


elif action == "delete":
    instanceId = findInstance()
    if not instanceId:
        print(f"Could not find instance with name {instanceName}")
        sys.exit(1)
    client.delete(f"/cloud/project/{serviceName}/instance/{instanceId}")
else:
    print("Invalid action. Use 'create' or 'delete'.")
