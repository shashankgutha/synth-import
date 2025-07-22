#!/usr/bin/env python3

import os
import sys
import json
import requests
from datetime import datetime
from pathlib import Path
import re

class SyntheticsImporter:
    def __init__(self, kibana_url, api_key, space_id='default'):
        self.kibana_url = kibana_url.rstrip('/')  # Remove trailing slash
        self.space_id = space_id
        self.monitors_dir = Path('monitors')
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'ApiKey {api_key}',
            'Content-Type': 'application/json',
            'kbn-xsrf': 'true'
        })

    def make_request(self, method, endpoint, data=None):
        """Make HTTP request to Kibana API"""
        url = f"{self.kibana_url}{endpoint}"
        
        try:
            if method.upper() == 'GET':
                response = self.session.get(url)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data)
            elif method.upper() == 'PUT':
                response = self.session.put(url, json=data)
            elif method.upper() == 'DELETE':
                response = self.session.delete(url)
            else:
                raise Exception(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            
            # Handle empty responses
            if response.status_code == 204 or not response.content:
                return {}
            
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Request failed: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse JSON response: {str(e)}")

    def get_existing_monitor(self, config_id):
        """Get existing monitor configuration if it exists"""
        try:
            print(f"Checking if monitor exists: {config_id}")
            response = self.make_request('GET', f"/api/synthetics/monitors/{config_id}")
            
            if response and response.get('config_id') == config_id:
                print(f"Monitor exists: {response.get('name', 'Unknown')} ({config_id})")
                return response
            else:
                print(f"Monitor not found: {config_id}")
                return None
                
        except Exception as e:
            # If we get a 404 or similar error, the monitor doesn't exist
            if "404" in str(e) or "Not Found" in str(e):
                print(f"Monitor not found: {config_id}")
                return None
            else:
                print(f"Error checking monitor {config_id}: {str(e)}")
                return None

    def merge_locations(self, existing_locations, new_locations):
        """Merge existing and new locations, avoiding duplicates"""
        merged_locations = existing_locations.copy()
        
        for new_location in new_locations:
            new_location_id = new_location.get('id')
            # Check if this location already exists
            if not any(loc.get('id') == new_location_id for loc in merged_locations):
                merged_locations.append(new_location)
                print(f"Adding new location: {new_location.get('label', new_location_id)}")
            else:
                print(f"Location already exists: {new_location.get('label', new_location_id)}")
        
        return merged_locations

    def find_monitor_files(self, changed_files_filter=None):
        """Find monitor JSON files in the monitors directory"""
        monitor_files = []
        
        if not self.monitors_dir.exists():
            print(f"Monitors directory '{self.monitors_dir}' does not exist")
            return monitor_files
        
        if changed_files_filter:
            # Process only specific changed files
            changed_file_list = changed_files_filter.strip().split('\n')
            changed_file_list = [f.strip() for f in changed_file_list if f.strip()]
            
            print(f"Processing {len(changed_file_list)} changed files:")
            for changed_file in changed_file_list:
                print(f"  - {changed_file}")
                
                file_path = Path(changed_file)
                if file_path.exists() and file_path.suffix == '.json':
                    # Extract location folder from path (monitors/location_folder/file.json)
                    if len(file_path.parts) >= 3 and file_path.parts[0] == 'monitors':
                        location_folder = file_path.parts[1]
                        monitor_files.append({
                            'file_path': file_path,
                            'location_folder': location_folder,
                            'filename': file_path.name
                        })
                    else:
                        print(f"  Warning: Skipping {changed_file} - invalid path structure")
                else:
                    print(f"  Warning: Skipping {changed_file} - file not found or not JSON")
        else:
            # Find all JSON files in location subdirectories (existing behavior)
            for location_dir in self.monitors_dir.iterdir():
                if location_dir.is_dir():
                    for json_file in location_dir.glob('*.json'):
                        monitor_files.append({
                            'file_path': json_file,
                            'location_folder': location_dir.name,
                            'filename': json_file.name
                        })
        
        print(f"Found {len(monitor_files)} monitor files to process")
        return monitor_files

    def load_monitor_config(self, file_path):
        """Load monitor configuration from JSON file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config
        except Exception as e:
            raise Exception(f"Failed to load monitor config from {file_path}: {str(e)}")

    def prepare_monitor_for_create(self, config):
        """Prepare monitor configuration for creation by removing specific fields"""
        # Create a copy to avoid modifying the original
        create_config = config.copy()
        
        # Remove fields that should not be sent during creation
        # Kibana will generate id and config_id automatically
        create_fields_to_remove = [
            'id', 'config_id', 'created_at', 'updated_at', 'spaceId', 'revision'
        ]
        
        # Only remove 'url' field for browser-type monitors
        if config.get('type') == 'browser':
            create_fields_to_remove.append('url')
        
        for field in create_fields_to_remove:
            create_config.pop(field, None)
        
        print(f"Removed fields for creation: {[f for f in create_fields_to_remove if f in config]}")
        return create_config
    
    def prepare_monitor_for_update(self, config):
        """Prepare monitor configuration for update by removing specific fields"""
        # Create a copy to avoid modifying the original
        update_config = config.copy()
        
        # Remove fields that should not be sent during update
        update_fields_to_remove = [
            'id', 'config_id', 'created_at', 'updated_at', 'revision', 'spaceId'
        ]
        
        for field in update_fields_to_remove:
            update_config.pop(field, None)
        
        return update_config

    def create_monitor(self, config):
        """Create a new monitor"""
        endpoint = f"/s/{self.space_id}/api/synthetics/monitors"
        
        # Prepare config for creation
        create_config = self.prepare_monitor_for_create(config)
        
        print(f"Creating monitor: {config.get('name', 'Unknown')}")
        
        try:
            response = self.make_request('POST', endpoint, create_config)
            return response
        except Exception as e:
            print(f"Failed to create monitor: {str(e)}")
            return None

    def update_monitor(self, config_id, config):
        """Update an existing monitor"""
        endpoint = f"/s/{self.space_id}/api/synthetics/monitors/{config_id}"
        
        # Prepare config for update
        update_config = self.prepare_monitor_for_update(config)
        
        print(f"Updating monitor: {config.get('name', 'Unknown')} (ID: {config_id})")
        
        try:
            response = self.make_request('PUT', endpoint, update_config)
            return response
        except Exception as e:
            print(f"Failed to update monitor: {str(e)}")
            return None



    def sanitize_filename(self, name):
        """Sanitize filename by replacing invalid characters"""
        return re.sub(r'[^a-zA-Z0-9.-]', '_', name)

    def import_monitors(self, dry_run=False, changed_files_filter=None, fresh_import=False):
        """Main import function"""
        try:
            # Find monitor files
            monitor_files = self.find_monitor_files(changed_files_filter)
            
            if not monitor_files:
                print("No monitor files found to import")
                return
            
            # Track import results
            results = {
                'created': [],
                'updated': [],
                'failed': [],
                'skipped': []
            }
            
            # Process each monitor file
            processed_configs = {}  # Track by config_id to merge locations
            
            # Separate new monitors (no config_id) from existing monitors
            new_monitors = []  # Monitors without config_id
            
            # First pass: collect all monitor configs and merge locations
            for file_info in monitor_files:
                try:
                    config = self.load_monitor_config(file_info['file_path'])
                    config_id = config.get('config_id')
                    monitor_name = config.get('name', 'Unknown')
                    
                    if not config_id:
                        # No config_id = new monitor, treat separately
                        print(f"No config_id found for {monitor_name} - treating as new monitor")
                        new_monitors.append({
                            'config': config,
                            'file_info': file_info
                        })
                        continue
                    
                    # If we've seen this monitor before, merge the locations
                    if config_id in processed_configs:
                        existing_config = processed_configs[config_id]['config']
                        current_locations = config.get('locations', [])
                        existing_locations = existing_config.get('locations', [])
                        
                        # Merge locations (avoid duplicates)
                        merged_locations = existing_locations.copy()
                        for location in current_locations:
                            if not any(loc.get('id') == location.get('id') for loc in merged_locations):
                                merged_locations.append(location)
                        
                        existing_config['locations'] = merged_locations
                        processed_configs[config_id]['files'].append(file_info)
                        print(f"Merged locations for {monitor_name}: {len(merged_locations)} total locations")
                    else:
                        # First time seeing this monitor
                        processed_configs[config_id] = {
                            'config': config,
                            'files': [file_info]
                        }
                        print(f"Processing {monitor_name} with {len(config.get('locations', []))} locations")
                
                except Exception as e:
                    print(f"Error loading {file_info['filename']}: {str(e)}")
                    results['failed'].append({
                        'file': str(file_info['file_path']),
                        'error': str(e)
                    })
            
            # Second pass: process new monitors (no config_id)
            print(f"\n=== Processing {len(new_monitors)} new monitors (no config_id) ===")
            for new_monitor in new_monitors:
                try:
                    config = new_monitor['config']
                    file_info = new_monitor['file_info']
                    monitor_name = config.get('name', 'Unknown')
                    locations = config.get('locations', [])
                    
                    print(f"\nCreating new monitor: {monitor_name}")
                    print(f"File: {file_info['filename']}")
                    print(f"Locations: {len(locations)}")
                    
                    if dry_run:
                        print(f"[DRY RUN] Would create new monitor: {monitor_name} with {len(locations)} locations")
                        results['created'].append({
                            'name': monitor_name, 
                            'config_id': 'new',
                            'file': str(file_info['file_path'])
                        })
                    else:
                        create_response = self.create_monitor(config)
                        if create_response:
                            new_config_id = create_response.get('config_id', 'generated')
                            print(f"✅ Successfully created new monitor with config_id: {new_config_id}")
                            results['created'].append({
                                'name': monitor_name,
                                'config_id': new_config_id,
                                'file': str(file_info['file_path'])
                            })
                        else:
                            print(f"❌ Failed to create new monitor: {monitor_name}")
                            results['failed'].append({
                                'file': str(file_info['file_path']),
                                'error': 'Failed to create new monitor'
                            })
                
                except Exception as e:
                    print(f"❌ Error creating new monitor from {file_info['filename']}: {str(e)}")
                    results['failed'].append({
                        'file': str(file_info['file_path']),
                        'error': str(e)
                    })
            
            # Third pass: process each unique monitor with all its locations (existing monitors)
            print(f"\n=== Processing {len(processed_configs)} existing monitors (with config_id) ===")
            for config_id, monitor_data in processed_configs.items():
                try:
                    config = monitor_data['config']
                    monitor_name = config.get('name', 'Unknown')
                    new_locations = config.get('locations', [])
                    
                    print(f"\nProcessing monitor: {monitor_name} ({config_id})")
                    print(f"New locations to deploy: {len(new_locations)}")
                    
                    if fresh_import:
                        # Fresh import mode - skip existence check and create directly
                        if dry_run:
                            print(f"[DRY RUN] Would create (fresh): {monitor_name} with {len(new_locations)} locations")
                            results['created'].append({'name': monitor_name, 'config_id': config_id})
                            continue
                        
                        print(f"Fresh import - creating monitor without existence check...")
                        create_response = self.create_monitor(config)
                        
                        if create_response is not None:
                            created_config_id = create_response.get('id') or create_response.get('config_id')
                            print(f"Monitor created successfully with ID: {created_config_id}")
                            
                            results['created'].append({
                                'name': monitor_name,
                                'config_id': created_config_id or config_id,
                                'total_locations': len(new_locations),
                                'operation': 'fresh_create'
                            })
                            print(f"Successfully created monitor (fresh import)")
                        else:
                            results['failed'].append({
                                'name': monitor_name,
                                'config_id': config_id,
                                'operation': 'fresh_create'
                            })
                        continue
                    
                    # Get existing monitor configuration (normal mode)
                    existing_monitor = self.get_existing_monitor(config_id)
                    
                    if dry_run:
                        if existing_monitor:
                            existing_locations = existing_monitor.get('locations', [])
                            merged_locations = self.merge_locations(existing_locations, new_locations)
                            print(f"[DRY RUN] Would update: {monitor_name} with {len(merged_locations)} total locations")
                            results['updated'].append({'name': monitor_name, 'config_id': config_id})
                        else:
                            print(f"[DRY RUN] Would create: {monitor_name} with {len(new_locations)} locations")
                            results['created'].append({'name': monitor_name, 'config_id': config_id})
                        continue
                    
                    # Perform actual create/update/restore workflow (normal mode)
                    if existing_monitor:
                        # Monitor exists - merge locations and update
                        print(f"Monitor exists, merging locations...")
                        existing_locations = existing_monitor.get('locations', [])
                        print(f"Existing locations: {len(existing_locations)}")
                        
                        # Merge existing and new locations
                        merged_locations = self.merge_locations(existing_locations, new_locations)
                        
                        # Update config with merged locations
                        config_to_update = config.copy()
                        config_to_update['locations'] = merged_locations
                        
                        print(f"Updating monitor with {len(merged_locations)} total locations")
                        response = self.update_monitor(config_id, config_to_update)
                        
                        if response is not None:
                            results['updated'].append({
                                'name': monitor_name,
                                'config_id': config_id,
                                'total_locations': len(merged_locations),
                                'operation': 'location_merge_update'
                            })
                            print(f"Successfully updated monitor with merged locations")
                        else:
                            results['failed'].append({
                                'name': monitor_name,
                                'config_id': config_id,
                                'operation': 'update_after_merge'
                            })
                    else:
                        # Monitor doesn't exist - create workflow
                        print(f"Monitor doesn't exist, creating new monitor...")
                        
                        # Create the monitor
                        print(f"Creating monitor...")
                        create_response = self.create_monitor(config)
                        
                        if create_response is not None:
                            created_config_id = create_response.get('id') or create_response.get('config_id')
                            print(f"Monitor created successfully with ID: {created_config_id}")
                            
                            results['created'].append({
                                'name': monitor_name,
                                'config_id': created_config_id or config_id,
                                'total_locations': len(new_locations),
                                'operation': 'create'
                            })
                            print(f"Successfully created monitor")
                        else:
                            results['failed'].append({
                                'name': monitor_name,
                                'config_id': config_id,
                                'operation': 'create'
                            })
                
                except Exception as e:
                    print(f"Error processing monitor {monitor_name}: {str(e)}")
                    results['failed'].append({
                        'name': monitor_name,
                        'config_id': config_id,
                        'error': str(e)
                    })
            
            # Print summary
            mode_text = ""
            if dry_run:
                mode_text = "DRY RUN "
            elif fresh_import:
                mode_text = "FRESH IMPORT "
            
            print(f"\n{mode_text}Import Summary:")
            print(f"{'=' * 50}")
            print(f"Total files processed: {len(monitor_files)}")
            print(f"New monitors (no config_id): {len(new_monitors)}")
            print(f"Existing monitors (with config_id): {len(processed_configs)}")
            print(f"Created: {len(results['created'])}")
            print(f"Updated: {len(results['updated'])}")
            print(f"Failed: {len(results['failed'])}")
            print(f"Skipped: {len(results['skipped'])}")
            
            if results['created']:
                print(f"\nCreated monitors:")
                for item in results['created']:
                    config_id_display = item.get('config_id', 'N/A')
                    if config_id_display == 'new':
                        config_id_display = 'new monitor'
                    file_info = f" - {Path(item['file']).name}" if 'file' in item else ""
                    print(f"   - {item['name']} ({config_id_display}){file_info}")
            
            if results['updated']:
                print(f"\nUpdated monitors:")
                for item in results['updated']:
                    print(f"   - {item['name']} ({item['config_id']})")
            
            if results['failed']:
                print(f"\nFailed operations:")
                for item in results['failed']:
                    print(f"   - {item.get('name', 'Unknown')} - {item.get('error', item.get('operation', 'Unknown error'))}")
            
            if results['skipped']:
                print(f"\nSkipped files:")
                for item in results['skipped']:
                    print(f"   - {Path(item['file']).name} - {item['reason']}")
            
            return results
            
        except Exception as e:
            print(f"Import failed: {str(e)}")
            sys.exit(1)

def main():
    """Main execution function"""
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Import Synthetics Monitors')
    parser.add_argument('--changed-files', action='store_true', 
                       help='Only process changed files from CHANGED_FILES environment variable')
    parser.add_argument('--fresh-import', action='store_true',
                       help='Fresh import mode - import all monitors without checking existence')
    args = parser.parse_args()
    
    kibana_url = os.getenv('KIBANA_URL')
    api_key = os.getenv('KIBANA_API_KEY')
    space_id = os.getenv('KIBANA_SPACE_ID', 'default')
    dry_run = os.getenv('DRY_RUN', 'false').lower() in ['true', '1', 'yes']
    changed_files = os.getenv('CHANGED_FILES', '').strip() if args.changed_files else None
    
    if not all([kibana_url, api_key]):
        print("Missing required environment variables:")
        print("- KIBANA_URL: Your Kibana instance URL")
        print("- KIBANA_API_KEY: Your Kibana API key")
        print("Optional:")
        print("- KIBANA_SPACE_ID: Kibana space ID (default: 'default')")
        print("- DRY_RUN: Set to 'true' for dry run mode")
        sys.exit(1)
    
    print(f"Kibana Synthetics Monitor Import")
    if args.fresh_import:
        print("FRESH IMPORT MODE - Importing all monitors without existence check")
    elif dry_run:
        print("DRY RUN MODE")
    else:
        print("LIVE MODE")
    if args.changed_files:
        print("CHANGED FILES MODE - Processing only modified monitors")
    print("=" * 50)
    print(f"Kibana URL: {kibana_url}")
    print(f"Space ID: {space_id}")
    if changed_files:
        print(f"Changed files: {changed_files}")
    print()
    
    importer = SyntheticsImporter(kibana_url, api_key, space_id)
    importer.import_monitors(dry_run=dry_run, changed_files_filter=changed_files, fresh_import=args.fresh_import)

if __name__ == "__main__":
    main()