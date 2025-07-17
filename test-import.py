#!/usr/bin/env python3
"""
Local testing script for Kibana Synthetics Monitor Import
"""

import os
import sys
from pathlib import Path

# Add the .github/scripts directory to Python path
sys.path.insert(0, str(Path(__file__).parent / '.github' / 'scripts'))

try:
    from import_synthetics_monitors import SyntheticsImporter
except ImportError:
    # If the import fails, try importing directly
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "import_synthetics_monitors", 
        Path(__file__).parent / '.github' / 'scripts' / 'import-synthetics-monitors.py'
    )
    import_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(import_module)
    SyntheticsImporter = import_module.SyntheticsImporter

def test_import_dry_run():
    """Test import in dry-run mode"""
    print("🧪 Testing import in DRY RUN mode...")
    print("=" * 50)
    
    kibana_url = os.getenv('KIBANA_URL')
    api_key = os.getenv('KIBANA_API_KEY')
    space_id = os.getenv('KIBANA_SPACE_ID', 'default')
    
    if not all([kibana_url, api_key]):
        print("❌ Missing required environment variables:")
        print("- KIBANA_URL: Your Kibana instance URL")
        print("- KIBANA_API_KEY: Your Kibana API key")
        return False
    
    try:
        importer = SyntheticsImporter(kibana_url, api_key, space_id)
        results = importer.import_monitors(dry_run=True)
        
        print("\n✅ Dry run completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Dry run failed: {str(e)}")
        return False

def test_monitor_files():
    """Test if monitor files are valid JSON"""
    print("🔍 Validating monitor files...")
    
    monitors_dir = Path('monitors')
    if not monitors_dir.exists():
        print("❌ Monitors directory not found")
        return False
    
    json_files = []
    for location_dir in monitors_dir.iterdir():
        if location_dir.is_dir():
            json_files.extend(location_dir.glob('*.json'))
    
    if not json_files:
        print("⚠️  No JSON files found in monitors directory")
        return False
    
    print(f"📁 Found {len(json_files)} monitor files")
    
    import json
    valid_files = 0
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Basic validation
            if 'name' not in config:
                print(f"⚠️  {json_file.name}: Missing 'name' field")
            elif 'type' not in config:
                print(f"⚠️  {json_file.name}: Missing 'type' field")
            else:
                print(f"✅ {json_file.name}: Valid ({config['type']} monitor)")
                valid_files += 1
                
        except json.JSONDecodeError as e:
            print(f"❌ {json_file.name}: Invalid JSON - {str(e)}")
        except Exception as e:
            print(f"❌ {json_file.name}: Error - {str(e)}")
    
    print(f"\n📊 Validation Summary: {valid_files}/{len(json_files)} files are valid")
    return valid_files == len(json_files)

def main():
    """Main testing function"""
    print("🚀 Kibana Synthetics Import - Local Testing")
    print("=" * 50)
    
    # Test monitor files first
    if not test_monitor_files():
        print("❌ Monitor file validation failed")
        return False
    
    print()
    
    # Test dry run import
    if not test_import_dry_run():
        print("❌ Import dry run failed")
        return False
    
    # Ask if user wants to run live import
    print("\n" + "=" * 50)
    response = input("🤔 Do you want to run LIVE import (this will modify Kibana)? (y/N): ").strip().lower()
    
    if response in ['y', 'yes']:
        print("\n🔥 Running LIVE import...")
        
        kibana_url = os.getenv('KIBANA_URL')
        api_key = os.getenv('KIBANA_API_KEY')
        space_id = os.getenv('KIBANA_SPACE_ID', 'default')
        
        try:
            importer = SyntheticsImporter(kibana_url, api_key, space_id)
            results = importer.import_monitors(dry_run=False)
            print("🎉 Live import completed!")
            
        except Exception as e:
            print(f"❌ Live import failed: {str(e)}")
            return False
    else:
        print("👍 Skipping live import. Dry run testing completed successfully!")
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)
    print("\n✨ All tests passed!")