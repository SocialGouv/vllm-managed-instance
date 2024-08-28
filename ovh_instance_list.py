import ovh
import json
import os

# Initialize OVH client
client = ovh.Client(
    endpoint=os.environ.get('OVH_ENDPOINT'),
    application_key=os.environ.get('OVH_APPLICATION_KEY'),
    application_secret=os.environ.get('OVH_APPLICATION_SECRET'),
    consumer_key=os.environ.get('OVH_CONSUMER_KEY')
)

def get_regions():
    return client.get('/cloud/project')

def get_flavors(project_id, region):
    return client.get(f'/cloud/project/{project_id}/region/{region}/flavor')

def get_images(project_id, region):
    return client.get(f'/cloud/project/{project_id}/region/{region}/image')

def main():
    result = {}
    projects = get_regions()

    for project_id in projects:
        regions = client.get(f'/cloud/project/{project_id}/region')
        
        for region in regions:
            if region not in result:
                result[region] = {
                    'flavors': [],
                    'images': []
                }
            
            flavors = get_flavors(project_id, region)
            images = get_images(project_id, region)
            
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