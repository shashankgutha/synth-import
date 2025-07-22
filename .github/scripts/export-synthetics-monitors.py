#!/usr/bin/env python3

import os
import sys
import json
import requests
import base64
from datetime import datetime
from pathlib import Path
import re

class SyntheticsExporter:
    def __init__(self, kibana_url, api_key, spaces=None):
        self.kibana_url = kibana_url.rstrip('/')  # Remove trailing slash
        self.output_dir = Path('monitors')
        self.spaces = spaces or ['default']  # Default to 'default' space if none provided
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'ApiKey {api_key}',
            'Content-Type': 'application/json',
            'kbn-xsrf': 'true'
        })

    def make_request(self, endpoint):
        """Make HTTP request to Kibana API"""
        url = f"{self.kibana_url}{endpoint}"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Request failed: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse JSON response: {str(e)}")

    def get_all_monitors(self, space_id='default'):
        """Fetch all synthetic monitors with pagination for a specific space"""
        print(f"Fetching all synthetic monitors from space: {space_id}")
        
        all_monitors = []
        page = 1
        total_monitors = 0
        
        while True:
            # Use space-specific endpoint
            endpoint = f"/s/{space_id}/api/synthetics/monitors?page={page}&perPage=50"
            response = self.make_request(endpoint)
            
            if page == 1:
                total_monitors = response.get('total', 0)
                print(f"Found {total_monitors} total monitors in space '{space_id}'")
            
            monitors = response.get('monitors', [])
            all_monitors.extend(monitors)
            print(f"Fetched page {page}, got {len(monitors)} monitors from space '{space_id}'")
            
            if len(all_monitors) >= total_monitors:
                break
                
            page += 1
        
        return all_monitors

    def get_monitor_config(self, config_id):
        """Fetch detailed configuration for a specific monitor"""
        print(f"Fetching detailed config for monitor: {config_id}")
        return self.make_request(f"/api/synthetics/monitors/{config_id}")

    def ensure_output_directory(self):
        """Create output directory if it doesn't exist"""
        if not self.output_dir.exists():
            self.output_dir.mkdir(parents=True, exist_ok=True)
            print(f"Created output directory: {self.output_dir}")

    def sanitize_filename(self, name):
        """Sanitize filename by replacing invalid characters"""
        return re.sub(r'[^a-zA-Z0-9.-]', '_', name)

    def export_monitors(self):
        """Main export function"""
        try:
            self.ensure_output_directory()
            
            all_exported_monitors = []
            all_location_summary = {}
            
            # Process each space
            for space_id in self.spaces:
                print(f"\n=== Processing space: {space_id} ===")
                
                # Get all monitors for this space
                monitors = self.get_all_monitors(space_id)
                
                if not monitors:
                    print(f"No monitors found in space '{space_id}'")
                    continue
            
            # Export each monitor's detailed configuration
            exported_monitors = []
            location_summary = {}
            
            for monitor in monitors:
                try:
                    config_id = monitor.get('config_id')
                    monitor_name = monitor.get('name', config_id)
                    
                    detailed_config = self.get_monitor_config(config_id)
                    
                    # Get locations from the detailed config
                    locations = detailed_config.get('locations', [])
                    
                    if not locations:
                        print(f"⚠️  Monitor '{monitor_name}' has no locations, skipping location-based export")
                        continue
                    
                    # Create filename from monitor name or config_id
                    base_filename = f"{self.sanitize_filename(monitor_name)}.json"
                    
                    monitor_locations = []
                    
                    # Export monitor to each location folder
                    for location in locations:
                        location_label = location.get('label', 'unknown-location')
                        location_id = location.get('id', 'unknown-id')
                        
                        # Sanitize location label for folder name
                        location_folder = self.sanitize_filename(location_label.replace('/', '_').replace(' - ', '_'))
                        
                        # Create space and location directory structure: monitors/{space_id}/{location}/
                        space_dir = self.output_dir / space_id
                        location_dir = space_dir / location_folder
                        location_dir.mkdir(parents=True, exist_ok=True)
                        
                        # Create monitor config specific to this location
                        location_specific_config = detailed_config.copy()
                        location_specific_config['locations'] = [location]  # Only this location
                        
                        # Write monitor configuration to location folder
                        location_file_path = location_dir / base_filename
                        with open(location_file_path, 'w', encoding='utf-8') as f:
                            json.dump(location_specific_config, f, indent=2, ensure_ascii=False)
                        
                        monitor_locations.append({
                            'location_id': location_id,
                            'location_label': location_label,
                            'location_folder': location_folder,
                            'filename': base_filename,
                            'file_path': f"{space_id}/{location_folder}/{base_filename}"
                        })
                        
                        # Track location summary
                        if location_folder not in location_summary:
                            location_summary[location_folder] = {
                                'location_label': location_label,
                                'location_id': location_id,
                                'monitors': []
                            }
                        location_summary[location_folder]['monitors'].append({
                            'name': monitor_name,
                            'config_id': config_id,
                            'filename': base_filename
                        })
                        
                        print(f"Exported: {monitor_name} -> {space_id}/{location_folder}/{base_filename}")
                    
                    exported_monitors.append({
                        'config_id': config_id,
                        'name': monitor_name,
                        'filename': base_filename,
                        'total_locations': len(locations),
                        'locations': monitor_locations
                    })
                    
                except Exception as e:
                    print(f"Failed to export monitor {monitor.get('config_id', 'unknown')}: {str(e)}")
            

            
                all_exported_monitors.extend(exported_monitors)
                all_location_summary.update(location_summary)
            
            print(f"\n=== Export Summary ===")
            print(f"Processed spaces: {', '.join(self.spaces)}")
            print(f"Total monitors exported: {len(all_exported_monitors)}")
            print(f"Total locations: {len(all_location_summary)}")
            print(f"Output directory: {self.output_dir}")
            
            # Show summary by space
            for space_id in self.spaces:
                space_locations = [loc for loc in all_location_summary.keys() if f"{space_id}/" in str(self.output_dir / space_id)]
                if space_locations:
                    print(f"Space '{space_id}': {len(space_locations)} locations")
            
            print(f"\nExport completed successfully!")
            
        except Exception as e:
            print(f"Export failed: {str(e)}")
            sys.exit(1)

def main():
    """Main execution function"""
    kibana_url = os.getenv('KIBANA_URL')
    api_key = os.getenv('KIBANA_API_KEY')
    kibana_spaces = os.getenv('KIBANA_SPACES', 'default')
    
    if not all([kibana_url, api_key]):
        print("Missing required environment variables:")
        print("- KIBANA_URL: Your Kibana instance URL")
        print("- KIBANA_API_KEY: Your Kibana API key")
        sys.exit(1)
    
    # Parse spaces (comma-separated list)
    spaces = [space.strip() for space in kibana_spaces.split(',') if space.strip()]
    print(f"Exporting monitors from spaces: {', '.join(spaces)}")
    
    exporter = SyntheticsExporter(kibana_url, api_key, spaces)
    exporter.export_monitors()

if __name__ == "__main__":
    main()