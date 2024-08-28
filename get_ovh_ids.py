import os
import sys
import ovh

def get_flavor_id(client, region, flavor_name):
    flavors = client.get(f'/cloud/project/{os.environ["OVH_SERVICE_NAME"]}/flavor', region=region)
    for flavor in flavors:
        if flavor['name'] == flavor_name:
            return flavor['id']
    raise ValueError(f"Flavor '{flavor_name}' not found in region '{region}'")

def get_image_id(client, region, image_name, flavor_id):
    images = client.get(f'/cloud/project/{os.environ["OVH_SERVICE_NAME"]}/image', 
                        flavorType=flavor_id, 
                        osType='linux', 
                        region=region)
    for image in images:
        if image['name'] == image_name:
            return image['id']
    raise ValueError(f"Image '{image_name}' not found for flavor '{flavor_id}' in region '{region}'")

def main():
    client = ovh.Client(
        endpoint=os.environ['OVH_ENDPOINT'],
        application_key=os.environ['OVH_APPLICATION_KEY'],
        application_secret=os.environ['OVH_APPLICATION_SECRET'],
        consumer_key=os.environ['OVH_CONSUMER_KEY']
    )

    region = os.environ['OVH_REGION']
    flavor_name = os.environ['OVH_INSTANCE_FLAVOR_NAME']
    image_name = os.environ['OVH_INSTANCE_IMAGE_NAME']

    try:
        flavor_id = get_flavor_id(client, region, flavor_name)
        image_id = get_image_id(client, region, image_name, flavor_id)

        # Set environment variables for the next step in the GitHub Actions workflow
        print(f"::set-output name=OVH_INSTANCE_FLAVOR_ID::{flavor_id}")
        print(f"::set-output name=OVH_INSTANCE_IMAGE_ID::{image_id}")
    except ValueError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()