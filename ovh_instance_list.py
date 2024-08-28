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

def get_projects(client):
    try:
        projects = client.get('/cloud/project')
        print(f"Retrieved {len(projects)} projects")
        return projects
    except Exception as e:
        print(f"Error fetching projects: {str(e)}")
        return []

def get_regions(client, project_id):
    try:
        regions = client.get(f'/cloud/project/{project_id}/region')
        print(f"Retrieved {len(regions)} regions for project {project_id}")
        return regions
    except Exception as e:
        print(f"Error fetching regions for project {project_id}: {str(e)}")
        return []

def get_flavors(client, project_id, region):
    try:
        flavors = client.get(f'/cloud/project/{project_id}/region/{region}/flavor')
        print(f"Retrieved {len(flavors)} flavors for project {project_id}, region {region}")
        return flavors
    except Exception as e:
        print(f"Error fetching flavors for project {project_id}, region {region}: {str(e)}")
        return []

def get_images(client, project_id, region):
    try:
        images = client.get(f'/cloud/project/{project_id}/region/{region}/image')
        print(f"Retrieved {len(images)} images for project {project_id}, region {region}")
        return images
    except Exception as e:
        print(f"Error fetching images for project {project_id}, region {region}: {str(e)}")
        return []

def main():
    client = initialize_ovh_client()
    result = {}
    projects = get_projects(client)

    if not projects:
        print("No projects found. Please check your OVH account and ensure you have the necessary permissions.")
        return

    for project_id in projects:
        regions = get_regions(client, project_id)
        
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
    print("\nOVH Instance Flavors and Images by Region:")
    print(json.dumps(result, indent=2))
    
    if result:
        print("\nResults have been saved to ovh_instance_list.json")
    else:
        print("\nNo data was retrieved. Please check your OVH account and permissions.")

if __name__ == "__main__":
    main()