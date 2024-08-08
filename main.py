import ovh
import os
import sys
from dotenv import load_dotenv

if len(sys.argv) != 2:
    print("Usage: python script.py <create|delete>")
    sys.exit(1)

action = sys.argv[1].lower()
load_dotenv()
client = ovh.Client()

serviceName = os.getenv("OVH_SERVICE_NAME")
sshKeyId = os.getenv("OVH_SSH_KEY_ID")
instanceName = "vllm-managed-instance"
flavorId = "906e8259-0340-4856-95b5-4ea2d26fe377"  # b2-7 GRA9
imageId = "1988cbfb-1f17-4b08-9391-666462b216af"  # Nvidia GPU Cloud GRA9
region = "GRA9"
userData = """
#cloud-config

packages:
  - apache2-utils
  - pwgen

write_files:
  - path: /home/ubuntu/init.sh
    permissions: "0755"
    content: |
        #!/bin/bash 

        set -Eeuo pipefail
        cd /home/ubuntu
        curl -O https://raw.githubusercontent.com/SocialGouv/vllm-managed-instance/main/docker-compose.yaml
        echo "HOST=$(curl -4 ifconfig.me)" >> .env
        export TOKEN=$(pwgen 32 1)
        echo "TOKEN=${TOKEN}" >> .env
        echo "CREDENTIALS=$(htpasswd -nBb user ${TOKEN})" >> .env
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


if action == "create":
    if findInstance():
        print(f"Instance with name {instanceName} already exists")
        sys.exit(1)
    instanceResponse = client.post(
        f"/cloud/project/{serviceName}/instance",
        name=instanceName,
        sshKeyId=sshKeyId,
        imageId=imageId,
        flavorId=flavorId,
        region=region,
        userData=userData,
    )
    print(instanceResponse)

elif action == "delete":
    instanceId = findInstance()
    if not instanceId:
        print(f"Could not find instance with name {instanceName}")
        sys.exit(1)
    client.delete(f"/cloud/project/{serviceName}/instance/{instanceId}")
else:
    print("Invalid action. Use 'create' or 'delete'.")
