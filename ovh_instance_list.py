import ovh
import json
import os
import sys

def initialize_ovh_client():
    endpoint = os.environ.get('OVH_ENDPOINT')
    application_key = os.environ.get('OVH_APPLICATION_KEY')
    application_secret = os.environ.get('OVH_APPLICATION_SECRET')
    consumer_key = os.environ.get('OVH_CONSUMER_KEY')

    if not all([endpoint, application_key, application_secret, consumer_key]):
        print("Error: Missing OVH API credentials. Please ensure all required environment variables are set.")
        print("Required variables: OVH_ENDPOINT, OVH_APPLICATION_KEY, OVH_APPLICATION_SECRET, OVH_CONSUMER_KEY")
        sys.exit(1)

    try:
        client = ovh.Client(
            endpoint=endpoint,
            application_key=application_key,
            application_secret=application_secret,
            consumer_key=consumer_key
        )
        print(f"Successfully initialized OVH client with endpoint: {endpoint}")
        return client
    except ovh.exceptions.InvalidRegion as e:
        print(f"Error: Invalid OVH endpoint. {str(e)}")
        print("Please ensure the OVH_ENDPOINT environment variable is set to a valid endpoint.")
        sys.exit(1)
    except Exception as e:
        print(f"Error initializing OVH client: {str(e)}")
        sys.exit(1)

def get_regions(client, service_name):
    try:
        regions = client.get(f'/cloud/project/{service_name}/region')
        print(f"Retrieved {len(regions)} regions for service {service_name}")
        return regions
    except Exception as e:
        print(f"Error fetching regions for service {service_name}: {str(e)}")
        return []

def get_flavors(client, service_name, region):
    try:
        flavors = client.get(f'/cloud/project/{service_name}/region/{region}/flavor')
        print(f"Retrieved {len(flavors)} flavors for service {service_name}, region {region}")
        return flavors
    except Exception as e:
        print(f"Error fetching flavors for service {service_name}, region {region}: {str(e)}")
        return []

def get_images(client, service_name, region):
    try:
        images = client.get(f'/cloud/project/{service_name}/region/{region}/image')
        print(f"Retrieved {len(images)} images for service {service_name}, region {region}")
        return images
    except Exception as e:
        print(f"Error fetching images for service {service_name}, region {region}: {str(e)}")
        return []

def main():
    client = initialize_ovh_client()
    service_name = os.environ.get('OVH_SERVICE_NAME')
    
    if not service_name:
        print("Error: OVH_SERVICE_NAME environment variable is not set.")
        sys.exit(1)

    print(f"Using OVH_SERVICE_NAME: {service_name}")
    
    result = {}
    regions = get_regions(client, service_name)

    if not regions:
        print("No regions found. Please check your OVH account and ensure you have the necessary permissions.")
        return

    for region in regions:
        result[region] = {
            'flavors': [],
            'images': []
        }
        
        flavors = get_flavors(client, service_name, region)
        images = get_images(client, service_name, region)
        
        result[region]['flavors'] = [flavor['id'] for flavor in flavors]
        result[region]['images'] = [image['id'] for image in images]
    
    # Write results to a JSON file
    with open('ovh_instance_list.json', 'w') as f:
        json.dump(result, f, indent=2)
    
    # Print results to console
    print("\nOVH Instance Flavors and Images by Region:")
    print(json.dumps(result, indent=2))
    
    if result:
        print("\nResults have been saved to ovh_instance_list.json")
    else:
        print("\nNo data was retrieved. Please check your OVH account and permissions.")

if __name__ == "__main__":
    main()