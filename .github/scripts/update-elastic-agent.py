#!/usr/bin/env python3

import os
import sys
import json
import requests
from pathlib import Path

class ElasticAgentUpdater:
    def __init__(self, kibana_url, api_key):
        self.kibana_url = kibana_url.rstrip('/')
        
        # Setup Kibana session
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'ApiKey {api_key}',
            'Content-Type': 'application/json',
            'kbn-xsrf': 'true'
        })



    def extract_agent_policy_id(self, folder_name):
        """Extract agentPolicyId from first JSON file in folder"""
        # folder_name is now in format "spaceid/location"
        folder_path = Path('monitors') / folder_name
        
        if not folder_path.exists():
            return None
        
        # Find first JSON file in folder
        json_files = list(folder_path.glob('*.json'))
        if not json_files:
            return None
        
        try:
            with open(json_files[0], 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Check root level first (backward compatibility)
                if 'agentPolicyId' in data:
                    return data['agentPolicyId']
                
                # Check in locations array
                locations = data.get('locations', [])
                for location in locations:
                    if 'agentPolicyId' in location:
                        return location['agentPolicyId']
                
                return None
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Error reading JSON file {json_files[0]}: {e}")
            return None

    def fetch_elastic_agent_config(self, agent_policy_id):
        """Fetch elastic-agent.yml from Kibana API"""
        try:
            url = f"{self.kibana_url}/api/fleet/agent_policies/{agent_policy_id}/download"
            response = self.session.get(url)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch elastic-agent.yml: {str(e)}")

    def process_k8s_secrets(self, config_content):
        """Process K8SSEC_ prefixed values and convert to Kubernetes ${} format"""
        import re
        
        # Pattern to match K8SSEC_ prefixed values (both quoted and unquoted)
        # Matches: K8SSEC_ES_USERNAME -> ES_USERNAME
        # Matches: "K8SSEC_ES_USERNAME" -> ${ES_USERNAME}
        pattern = r'"?K8SSEC_([A-Z_][A-Z0-9_]*)"?'
        
        def replace_k8s_secret(match):
            secret_name = match.group(1)  # Extract the part after K8SSEC_
            return f"${{{secret_name}}}"
        
        # Replace all K8SSEC_ patterns with ${} format
        processed_content = re.sub(pattern, replace_k8s_secret, config_content)
        
        # Count replacements for logging
        matches = re.findall(r'K8SSEC_([A-Z_][A-Z0-9_]*)', config_content)
        if matches:
            print(f"Converted {len(matches)} K8SSEC_ references to Kubernetes secrets:")
            for match in matches:
                print(f"  K8SSEC_{match} -> ${{{match}}}")
        
        return processed_content

    def update_elastic_agent_file(self, folder_name, config_content):
        """Update elastic-agent.yml file in specified folder"""
        # folder_name is now in format "spaceid/location"
        file_path = Path('monitors') / folder_name / 'elastic-agent.yml'
        
        try:
            # Process K8SSEC_ references for Kubernetes compatibility
            processed_content = self.process_k8s_secrets(config_content)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(processed_content)
            return True
        except Exception as e:
            print(f"Error writing file {file_path}: {e}")
            return False

    def update_elastic_agent_configs(self, changed_folders):
        """Main function to update elastic agent configurations"""
        print("Starting Elastic Agent configuration update...")
        
        if not changed_folders:
            print("No monitor folders provided for update")
            return
        
        print(f"Processing {len(changed_folders)} folders: {', '.join(changed_folders)}")
        
        updated_folders = []
        
        for folder_name in changed_folders:
            try:
                print(f"\nProcessing folder: {folder_name}")
                
                # Extract agent policy ID
                agent_policy_id = self.extract_agent_policy_id(folder_name)
                if not agent_policy_id:
                    raise Exception(f"Could not find agentPolicyId in JSON files for folder: {folder_name}")
                
                print(f"Found agent policy ID: {agent_policy_id}")
                
                # Fetch elastic-agent.yml from API
                config_content = self.fetch_elastic_agent_config(agent_policy_id)
                print(f"Fetched elastic-agent.yml config ({len(config_content)} characters)")
                
                # Update file
                if not self.update_elastic_agent_file(folder_name, config_content):
                    raise Exception(f"Failed to write elastic-agent.yml file for folder: {folder_name}")
                
                print(f"✅ Successfully updated elastic-agent.yml for {folder_name}")
                updated_folders.append(folder_name)
                    
            except Exception as e:
                print(f"❌ Error processing folder {folder_name}: {str(e)}")
                sys.exit(1)
        
        print(f"\n✅ Successfully updated {len(updated_folders)} folders: {', '.join(updated_folders)}")

def main():
    """Main execution function"""
    kibana_url = os.getenv('KIBANA_URL')
    api_key = os.getenv('KIBANA_API_KEY')
    
    if not all([kibana_url, api_key]):
        print("Missing required environment variables:")
        print("- KIBANA_URL: Your Kibana instance URL")
        print("- KIBANA_API_KEY: Your Kibana API key")
        sys.exit(1)
    
    # Get changed folders from command line arguments
    if len(sys.argv) < 2:
        print("No changed folders provided as command line arguments")
        sys.exit(1)
    
    changed_folders = sys.argv[1:]  # All arguments after script name
    updater = ElasticAgentUpdater(kibana_url, api_key)
    updater.update_elastic_agent_configs(changed_folders)

if __name__ == "__main__":
    main()