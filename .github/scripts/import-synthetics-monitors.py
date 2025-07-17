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
            print(f"🔍 Checking if monitor exists: {config_id}")
            response = self.make_request('GET', f"/api/synthetics/monitors/{config_id}")
            
            if response and response.get('config_id') == config_id:
                print(f"✅ Monitor exists: {response.get('name', 'Unknown')} ({config_id})")
                return response
            else:
                print(f"❌ Monitor not found: {config_id}")
                return None
                
        except Exception as e:
            # If we get a 404 or similar error, the monitor doesn't exist
            if "404" in str(e) or "Not Found" in str(e):
                print(f"❌ Monitor not found: {config_id}")
                return None
            else:
                print(f"⚠️  Error checking monitor {config_id}: {str(e)}")
                return None

    def merge_locations(self, existing_locations, new_locations):
        """Merge existing and new locations, avoiding duplicates"""
        merged_locations = existing_locations.copy()
        
        for new_location in new_locations:
            new_location_id = new_location.get('id')
            # Check if this location already exists
            if not any(loc.get('id') == new_location_id for loc in merged_locations):
                merged_locations.append(new_location)
                print(f"➕ Adding new location: {new_location.get('label', new_location_id)}")
            else:
                print(f"🔄 Location already exists: {new_location.get('label', new_location_id)}")
        
        return merged_locations

    def find_monitor_files(self):
        """Find all monitor JSON files in the monitors directory"""
        monitor_files = []
        
        if not self.monitors_dir.exists():
            print(f"❌ Monitors directory '{self.monitors_dir}' does not exist")
            return monitor_files
        
        # Find all JSON files in location subdirectories
        for location_dir in self.monitors_dir.iterdir():
            if location_dir.is_dir():
                for json_file in location_dir.glob('*.json'):
                    monitor_files.append({
                        'file_path': json_file,
                        'location_folder': location_dir.name,
                        'filename': json_file.name
                    })
        
        print(f"📁 Found {len(monitor_files)} monitor files across locations")
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
        
        print(f"🔧 Removed fields for creation: {[f for f in create_fields_to_remove if f in config]}")
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
        
        print(f"📝 Creating monitor: {config.get('name', 'Unknown')}")
        
        try:
            response = self.make_request('POST', endpoint, create_config)
            return response
        except Exception as e:
            print(f"❌ Failed to create monitor: {str(e)}")
            return None

    def update_monitor(self, config_id, config):
        """Update an existing monitor"""
        endpoint = f"/s/{self.space_id}/api/synthetics/monitors/{config_id}"
        
        # Prepare config for update
        update_config = self.prepare_monitor_for_update(config)
        
        print(f"🔄 Updating monitor: {config.get('name', 'Unknown')} (ID: {config_id})")
        
        try:
            response = self.make_request('PUT', endpoint, update_config)
            return response
        except Exception as e:
            print(f"❌ Failed to update monitor: {str(e)}")
            return None

    def update_json_files_with_new_config(self, file_infos, new_monitor_config):
        """Update JSON files with the new monitor configuration from Kibana"""
        try:
            for file_info in file_infos:
                file_path = file_info['file_path']
                location_folder = file_info['location_folder']
                
                print(f"📝 Updating {file_path.name} in {location_folder}")
                
                # Create location-specific config (only include the location for this folder)
                location_specific_config = new_monitor_config.copy()
                
                # Find the location that matches this folder
                all_locations = new_monitor_config.get('locations', [])
                folder_location = None
                
                for location in all_locations:
                    location_label = location.get('label', 'unknown-location')
                    sanitized_label = self.sanitize_filename(location_label.replace('/', '_').replace(' - ', '_'))
                    
                    if sanitized_label == location_folder:
                        folder_location = location
                        break
                
                if folder_location:
                    # Update config to only include this location
                    location_specific_config['locations'] = [folder_location]
                    
                    # Write updated config back to file
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(location_specific_config, f, indent=2, ensure_ascii=False)
                    
                    print(f"✅ Updated {file_path.name} with new config_id: {new_monitor_config.get('config_id')}")
                else:
                    print(f"⚠️  Could not find matching location for folder: {location_folder}")
                    
        except Exception as e:
            print(f"❌ Error updating JSON files: {str(e)}")

    def sanitize_filename(self, name):
        """Sanitize filename by replacing invalid characters"""
        return re.sub(r'[^a-zA-Z0-9.-]', '_', name)

    def import_monitors(self, dry_run=False):
        """Main import function"""
        try:
            # Find monitor files
            monitor_files = self.find_monitor_files()
            
            if not monitor_files:
                print("⚠️  No monitor files found to import")
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
            
            # First pass: collect all monitor configs and merge locations
            for file_info in monitor_files:
                try:
                    config = self.load_monitor_config(file_info['file_path'])
                    config_id = config.get('config_id')
                    monitor_name = config.get('name', 'Unknown')
                    
                    if not config_id:
                        print(f"⚠️  Skipping {file_info['filename']} - no config_id found")
                        results['skipped'].append({
                            'file': str(file_info['file_path']),
                            'reason': 'No config_id'
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
                        print(f"🔗 Merged locations for {monitor_name}: {len(merged_locations)} total locations")
                    else:
                        # First time seeing this monitor
                        processed_configs[config_id] = {
                            'config': config,
                            'files': [file_info]
                        }
                        print(f"📋 Processing {monitor_name} with {len(config.get('locations', []))} locations")
                
                except Exception as e:
                    print(f"❌ Error loading {file_info['filename']}: {str(e)}")
                    results['failed'].append({
                        'file': str(file_info['file_path']),
                        'error': str(e)
                    })
            
            # Second pass: process each unique monitor with all its locations
            for config_id, monitor_data in processed_configs.items():
                try:
                    config = monitor_data['config']
                    monitor_name = config.get('name', 'Unknown')
                    new_locations = config.get('locations', [])
                    
                    print(f"\n🎯 Processing monitor: {monitor_name} ({config_id})")
                    print(f"📍 New locations to deploy: {len(new_locations)}")
                    
                    # Get existing monitor configuration
                    existing_monitor = self.get_existing_monitor(config_id)
                    
                    if dry_run:
                        if existing_monitor:
                            existing_locations = existing_monitor.get('locations', [])
                            merged_locations = self.merge_locations(existing_locations, new_locations)
                            print(f"🔄 [DRY RUN] Would update: {monitor_name} with {len(merged_locations)} total locations")
                            results['updated'].append({'name': monitor_name, 'config_id': config_id})
                        else:
                            print(f"📝 [DRY RUN] Would create: {monitor_name} with {len(new_locations)} locations")
                            results['created'].append({'name': monitor_name, 'config_id': config_id})
                        continue
                    
                    # Perform actual create/update/restore workflow
                    if existing_monitor:
                        # Monitor exists - merge locations and update
                        print(f"✅ Monitor exists, merging locations...")
                        existing_locations = existing_monitor.get('locations', [])
                        print(f"📍 Existing locations: {len(existing_locations)}")
                        
                        # Merge existing and new locations
                        merged_locations = self.merge_locations(existing_locations, new_locations)
                        
                        # Update config with merged locations
                        config_to_update = config.copy()
                        config_to_update['locations'] = merged_locations
                        
                        print(f"🔄 Updating monitor with {len(merged_locations)} total locations")
                        response = self.update_monitor(config_id, config_to_update)
                        
                        if response is not None:
                            results['updated'].append({
                                'name': monitor_name,
                                'config_id': config_id,
                                'total_locations': len(merged_locations),
                                'operation': 'location_merge_update'
                            })
                            print(f"✅ Successfully updated monitor with merged locations")
                        else:
                            results['failed'].append({
                                'name': monitor_name,
                                'config_id': config_id,
                                'operation': 'update_after_merge'
                            })
                    else:
                        # Monitor doesn't exist - create then update workflow
                        print(f"❌ Monitor doesn't exist, starting create-then-update workflow...")
                        
                        # Step 1: Create the monitor
                        print(f"📝 Step 1: Creating monitor...")
                        create_response = self.create_monitor(config)
                        
                        if create_response is not None:
                            created_config_id = create_response.get('id') or create_response.get('config_id')
                            print(f"✅ Monitor created successfully with ID: {created_config_id}")
                            
                            # Step 2: Get the created monitor to ensure we have the complete config
                            print(f"🔍 Step 2: Fetching created monitor...")
                            created_monitor = self.get_existing_monitor(created_config_id or config_id)
                            
                            if created_monitor:
                                # Step 3: Update the created monitor with the complete configuration
                                print(f"🔄 Step 3: Updating created monitor with complete config...")
                                update_response = self.update_monitor(created_config_id or config_id, config)
                                
                                if update_response is not None:
                                    # Step 4: Update JSON files with the new monitor configuration
                                    print(f"📝 Step 4: Updating JSON files with new monitor config...")
                                    self.update_json_files_with_new_config(monitor_data['files'], created_monitor)
                                    
                                    results['created'].append({
                                        'name': monitor_name,
                                        'config_id': created_config_id or config_id,
                                        'total_locations': len(new_locations),
                                        'operation': 'create_then_update'
                                    })
                                    print(f"✅ Successfully created, updated, and saved monitor")
                                else:
                                    results['failed'].append({
                                        'name': monitor_name,
                                        'config_id': config_id,
                                        'operation': 'update_after_create'
                                    })
                            else:
                                results['failed'].append({
                                    'name': monitor_name,
                                    'config_id': config_id,
                                    'operation': 'fetch_after_create'
                                })
                        else:
                            results['failed'].append({
                                'name': monitor_name,
                                'config_id': config_id,
                                'operation': 'create'
                            })
                
                except Exception as e:
                    print(f"❌ Error processing monitor {monitor_name}: {str(e)}")
                    results['failed'].append({
                        'name': monitor_name,
                        'config_id': config_id,
                        'error': str(e)
                    })
            
            # Print summary
            print(f"\n{'🧪 DRY RUN ' if dry_run else ''}Import Summary:")
            print(f"{'=' * 50}")
            print(f"📝 Created: {len(results['created'])}")
            print(f"🔄 Updated: {len(results['updated'])}")
            print(f"❌ Failed: {len(results['failed'])}")
            print(f"⚠️  Skipped: {len(results['skipped'])}")
            
            if results['created']:
                print(f"\n📝 Created monitors:")
                for item in results['created']:
                    print(f"   - {item['name']} ({item.get('config_id', 'N/A')})")
            
            if results['updated']:
                print(f"\n🔄 Updated monitors:")
                for item in results['updated']:
                    print(f"   - {item['name']} ({item['config_id']})")
            
            if results['failed']:
                print(f"\n❌ Failed operations:")
                for item in results['failed']:
                    print(f"   - {item.get('name', 'Unknown')} - {item.get('error', item.get('operation', 'Unknown error'))}")
            
            if results['skipped']:
                print(f"\n⚠️  Skipped files:")
                for item in results['skipped']:
                    print(f"   - {Path(item['file']).name} - {item['reason']}")
            
            return results
            
        except Exception as e:
            print(f"Import failed: {str(e)}")
            sys.exit(1)

def main():
    """Main execution function"""
    kibana_url = os.getenv('KIBANA_URL')
    api_key = os.getenv('KIBANA_API_KEY')
    space_id = os.getenv('KIBANA_SPACE_ID', 'default')
    dry_run = os.getenv('DRY_RUN', 'false').lower() in ['true', '1', 'yes']
    
    if not all([kibana_url, api_key]):
        print("Missing required environment variables:")
        print("- KIBANA_URL: Your Kibana instance URL")
        print("- KIBANA_API_KEY: Your Kibana API key")
        print("Optional:")
        print("- KIBANA_SPACE_ID: Kibana space ID (default: 'default')")
        print("- DRY_RUN: Set to 'true' for dry run mode")
        sys.exit(1)
    
    print(f"🚀 Kibana Synthetics Monitor Import")
    print(f"{'🧪 DRY RUN MODE' if dry_run else '🔥 LIVE MODE'}")
    print("=" * 50)
    print(f"🌐 Kibana URL: {kibana_url}")
    print(f"🏠 Space ID: {space_id}")
    print()
    
    importer = SyntheticsImporter(kibana_url, api_key, space_id)
    importer.import_monitors(dry_run=dry_run)

if __name__ == "__main__":
    main()