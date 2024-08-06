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
flavorId = "e81b46f8-1159-4e14-b0ba-cad655e6540b"  # b3-8
imageId = "0192bfbe-952d-4c28-8264-4301cba17e56"  # Nvidia GPU Cloud
region = "GRA11"
userData = """
#cloud-config

runcmd:
- touch /home/ubuntu/bonjour
"""


def findInstance():
    instances = client.get(f"/cloud/project/{serviceName}/instance")
    if not instances:
        print("Could not get available instances")
        sys.exit(1)
    found = False
    for instance in instances:
        if not instance["name"] == instanceName:
            continue
        return instance["id"]
    if not found:
        return None


if action == "create":
    if findInstance():
        print(f"Instance with name {instanceName} already exists")
        sys.exit(1)
    response = client.post(
        f"/cloud/project/{serviceName}/instance",
        name=instanceName,
        sshKeyId=sshKeyId,
        imageId=imageId,
        flavorId=flavorId,
        region=region,
        userData=userData,
    )
    print(response)
elif action == "delete":
    instanceId = findInstance()
    if not instanceId:
        print(f"Could not find instance with name {instanceName}")
        sys.exit(1)
    client.delete(f"/cloud/project/{serviceName}/instance/{instanceId}")
else:
    print("Invalid action. Use 'create' or 'delete'.")
