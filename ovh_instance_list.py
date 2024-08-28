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
        return ovh.Client(
            endpoint=endpoint,
            application_key=application_key,
            application_secret=application_secret,
            consumer_key=consumer_key
        )
    except ovh.exceptions.InvalidRegion as e:
        print(f"Error: Invalid OVH endpoint. {str(e)}")
        print("Please ensure the OVH_ENDPOINT environment variable is set to a valid endpoint.")
        sys.exit(1)
    except Exception as e:
        print(f"Error initializing OVH client: {str(e)}")
        sys.exit(1)

def get_regions(client):
    try:
        return client.get('/cloud/project')
    except Exception as e:
        print(f"Error fetching regions: {str(e)}")
        return []

def get_flavors(client, project_id, region):
    try:
        return client.get(f'/cloud/project/{project_id}/region/{region}/flavor')
    except Exception as e:
        print(f"Error fetching flavors for project {project_id}, region {region}: {str(e)}")
        return []

def get_images(client, project_id, region):
    try:
        return client.get(f'/cloud/project/{project_id}/region/{region}/image')
    except Exception as e:
        print(f"Error fetching images for project {project_id}, region {region}: {str(e)}")
        return []

def main():
    client = initialize_ovh_client()
    result = {}
    projects = get_regions(client)

    for project_id in projects:
        try:
            regions = client.get(f'/cloud/project/{project_id}/region')
        except Exception as e:
            print(f"Error fetching regions for project {project_id}: {str(e)}")
            continue
        
        for region in regions:
            if region not in result:
                result[region] = {
                    'flavors': [],
                    'images': []
                }
            
            flavors = get_flavors(client, project_id, region)
            images = get_images(client, project_id, region)
            
            result[region]['flavors'].extend([flavor['id'] for flavor in flavors])
            result[region]['images'].extend([image['id'] for image in images])
    
    # Remove duplicates
    for region in result:
        result[region]['flavors'] = list(set(result[region]['flavors']))
        result[region]['images'] = list(set(result[region]['images']))
    
    # Write results to a JSON file
    with open('ovh_instance_list.json', 'w') as f:
        json.dump(result, f, indent=2)
    
    # Print results to console
    print("OVH Instance Flavors and Images by Region:")
    print(json.dumps(result, indent=2))
    
    print("\nResults have been saved to ovh_instance_list.json")

if __name__ == "__main__":
    main()