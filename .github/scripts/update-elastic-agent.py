#!/usr/bin/env python3

import os
import sys
import json
import requests
import subprocess
from pathlib import Path
from datetime import datetime

class ElasticAgentUpdater:
    def __init__(self, kibana_url, api_key, github_token, pr_number, repo_owner, repo_name):
        self.kibana_url = kibana_url.rstrip('/')
        self.github_token = github_token
        self.pr_number = pr_number
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        
        # Setup Kibana session
        self.kibana_session = requests.Session()
        self.kibana_session.headers.update({
            'Authorization': f'ApiKey {api_key}',
            'Content-Type': 'application/json',
            'kbn-xsrf': 'true'
        })
        
        # Setup GitHub session
        self.github_session = requests.Session()
        self.github_session.headers.update({
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        })

    def get_changed_folders(self):
        """Get list of monitor folders that had JSON changes"""
        try:
            # Get changed files in this PR
            result = subprocess.run([
                'git', 'diff', '--name-only', 'origin/main...HEAD'
            ], capture_output=True, text=True, check=True)
            
            changed_files = result.stdout.strip().split('\n')
            changed_folders = set()
            
            for file_path in changed_files:
                if file_path.startswith('monitors/') and file_path.endswith('.json'):
                    # Extract folder path (e.g., monitors/test_loc/google.json -> test_loc)
                    parts = file_path.split('/')
                    if len(parts) >= 3:
                        folder_name = parts[1]
                        changed_folders.add(folder_name)
            
            return list(changed_folders)
        except subprocess.CalledProcessError as e:
            print(f"Error getting changed files: {e}")
            return []

    def extract_agent_policy_id(self, folder_name):
        """Extract agentPolicyId from first JSON file in folder"""
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
                return data.get('agentPolicyId')
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Error reading JSON file {json_files[0]}: {e}")
            return None

    def fetch_elastic_agent_config(self, agent_policy_id):
        """Fetch elastic-agent.yml from Kibana API"""
        try:
            url = f"{self.kibana_url}/api/fleet/agent_policies/{agent_policy_id}/download"
            response = self.kibana_session.get(url)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch elastic-agent.yml: {str(e)}")

    def update_elastic_agent_file(self, folder_name, config_content):
        """Update elastic-agent.yml file in specified folder"""
        file_path = Path('monitors') / folder_name / 'elastic-agent.yml'
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(config_content)
            return True
        except Exception as e:
            print(f"Error writing file {file_path}: {e}")
            return False

    def get_monitor_names_in_folder(self, folder_name):
        """Get list of monitor names (JSON files) in folder"""
        folder_path = Path('monitors') / folder_name
        json_files = list(folder_path.glob('*.json'))
        return [f.stem for f in json_files]

    def post_pr_comment(self, message):
        """Post comment to PR"""
        try:
            url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/issues/{self.pr_number}/comments"
            data = {"body": message}
            response = self.github_session.post(url, json=data)
            response.raise_for_status()
            print("Posted PR comment successfully")
        except requests.exceptions.RequestException as e:
            print(f"Failed to post PR comment: {e}")

    def run(self):
        """Main execution function"""
        print("Starting Elastic Agent configuration update...")
        
        # Get changed folders
        changed_folders = self.get_changed_folders()
        
        if not changed_folders:
            print("No monitor folders with JSON changes found")
            return
        
        print(f"Found {len(changed_folders)} folders with JSON changes: {', '.join(changed_folders)}")
        
        success_results = []
        error_results = []
        
        for folder_name in changed_folders:
            try:
                print(f"\nProcessing folder: {folder_name}")
                
                # Extract agent policy ID
                agent_policy_id = self.extract_agent_policy_id(folder_name)
                if not agent_policy_id:
                    error_msg = f"Could not find agentPolicyId in JSON files for folder: {folder_name}"
                    print(f"❌ {error_msg}")
                    error_results.append({
                        'folder': folder_name,
                        'error': error_msg
                    })
                    continue
                
                print(f"Found agent policy ID: {agent_policy_id}")
                
                # Fetch elastic-agent.yml from API
                config_content = self.fetch_elastic_agent_config(agent_policy_id)
                print(f"Fetched elastic-agent.yml config ({len(config_content)} characters)")
                
                # Update file
                if self.update_elastic_agent_file(folder_name, config_content):
                    monitor_names = self.get_monitor_names_in_folder(folder_name)
                    print(f"✅ Successfully updated elastic-agent.yml for {folder_name}")
                    success_results.append({
                        'folder': folder_name,
                        'policy_id': agent_policy_id,
                        'monitors': monitor_names
                    })
                else:
                    error_msg = f"Failed to write elastic-agent.yml file for folder: {folder_name}"
                    print(f"❌ {error_msg}")
                    error_results.append({
                        'folder': folder_name,
                        'error': error_msg
                    })
                    
            except Exception as e:
                error_msg = f"Error processing folder {folder_name}: {str(e)}"
                print(f"❌ {error_msg}")
                error_results.append({
                    'folder': folder_name,
                    'error': error_msg
                })
        
        # Generate PR comment
        self.generate_pr_comment(success_results, error_results)

    def generate_pr_comment(self, success_results, error_results):
        """Generate and post PR comment with results"""
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        
        comment_parts = [
            "## 🔄 Elastic Agent Configuration Update Results",
            f"*Updated at: {timestamp}*",
            ""
        ]
        
        if success_results:
            comment_parts.extend([
                "### ✅ Successfully Updated Locations",
                ""
            ])
            
            for result in success_results:
                folder = result['folder']
                policy_id = result['policy_id']
                monitors = result['monitors']
                
                comment_parts.extend([
                    f"**📍 {folder}**",
                    f"- Agent Policy ID: `{policy_id}`",
                    f"- Monitors: {', '.join([f'`{m}`' for m in monitors])}",
                    f"- File: `monitors/{folder}/elastic-agent.yml`",
                    ""
                ])
        
        if error_results:
            comment_parts.extend([
                "### ❌ Errors Encountered",
                ""
            ])
            
            for result in error_results:
                folder = result['folder']
                error = result['error']
                
                comment_parts.extend([
                    f"**📍 {folder}**",
                    f"- Error: {error}",
                    ""
                ])
        
        if not success_results and not error_results:
            comment_parts.extend([
                "### ℹ️ No Changes Required",
                "No monitor folders with JSON changes were found that required elastic-agent.yml updates.",
                ""
            ])
        
        # Add summary
        total_processed = len(success_results) + len(error_results)
        comment_parts.extend([
            "---",
            f"**Summary:** {len(success_results)} successful, {len(error_results)} errors, {total_processed} total locations processed"
        ])
        
        comment = "\n".join(comment_parts)
        self.post_pr_comment(comment)

def main():
    """Main execution function"""
    required_vars = ['KIBANA_URL', 'KIBANA_API_KEY', 'GITHUB_TOKEN', 'PR_NUMBER', 'REPO_OWNER', 'REPO_NAME']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)
    
    updater = ElasticAgentUpdater(
        kibana_url=os.getenv('KIBANA_URL'),
        api_key=os.getenv('KIBANA_API_KEY'),
        github_token=os.getenv('GITHUB_TOKEN'),
        pr_number=os.getenv('PR_NUMBER'),
        repo_owner=os.getenv('REPO_OWNER'),
        repo_name=os.getenv('REPO_NAME')
    )
    
    updater.run()

if __name__ == "__main__":
    main()