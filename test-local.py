#!/usr/bin/env python3
"""
Local testing script for Kibana Synthetics Monitor Export
This script helps test the export functionality with additional debugging
"""

import os
import sys
from pathlib import Path

# Add the .github/scripts directory to Python path so we can import our module
sys.path.insert(0, str(Path(__file__).parent / '.github' / 'scripts'))

try:
    from export_synthetics_monitors import SyntheticsExporter
except ImportError:
    # If the import fails, try importing directly
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "export_synthetics_monitors", 
        Path(__file__).parent / '.github' / 'scripts' / 'export-synthetics-monitors.py'
    )
    export_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(export_module)
    SyntheticsExporter = export_module.SyntheticsExporter

def test_connection(kibana_url, api_key):
    """Test basic connection to Kibana API"""
    print("🔍 Testing connection to Kibana...")
    
    try:
        exporter = SyntheticsExporter(kibana_url, api_key)
        
        # Test basic API connectivity
        response = exporter.make_request("/api/synthetics/monitors?page=1&perPage=1")
        print("✅ Connection successful!")
        print(f"📊 API Response keys: {list(response.keys())}")
        
        total_monitors = response.get('total', 0)
        print(f"📈 Total monitors found: {total_monitors}")
        
        if total_monitors > 0:
            monitors = response.get('monitors', [])
            if monitors:
                first_monitor = monitors[0]
                print(f"🎯 First monitor sample:")
                print(f"   - Config ID: {first_monitor.get('config_id', 'N/A')}")
                print(f"   - Name: {first_monitor.get('name', 'N/A')}")
                print(f"   - Type: {first_monitor.get('type', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {str(e)}")
        return False

def test_single_monitor_export(kibana_url, api_key):
    """Test exporting a single monitor for debugging"""
    print("\n🧪 Testing single monitor export...")
    
    try:
        exporter = SyntheticsExporter(kibana_url, api_key)
        
        # Get first monitor
        response = exporter.make_request("/api/synthetics/monitors?page=1&perPage=1")
        monitors = response.get('monitors', [])
        
        if not monitors:
            print("⚠️  No monitors found to test with")
            return False
        
        test_monitor = monitors[0]
        config_id = test_monitor.get('config_id')
        
        print(f"🎯 Testing with monitor: {test_monitor.get('name', config_id)}")
        
        # Get detailed config
        detailed_config = exporter.get_monitor_config(config_id)
        print("✅ Successfully retrieved detailed monitor configuration")
        print(f"📋 Config keys: {list(detailed_config.keys())}")
        
        return True
        
    except Exception as e:
        print(f"❌ Single monitor test failed: {str(e)}")
        return False

def main():
    """Main testing function"""
    print("🚀 Kibana Synthetics Export - Local Testing")
    print("=" * 50)
    
    # Check environment variables
    kibana_url = os.getenv('KIBANA_URL')
    api_key = os.getenv('KIBANA_API_KEY')
    
    if not kibana_url:
        print("❌ KIBANA_URL environment variable not set")
        print("💡 Set it with: set KIBANA_URL=https://your-kibana-instance.com")
        return False
    
    if not api_key:
        print("❌ KIBANA_API_KEY environment variable not set")
        print("💡 Set it with: set KIBANA_API_KEY=your-api-key")
        return False
    
    print(f"🌐 Kibana URL: {kibana_url}")
    print(f"🔑 API Key: {'*' * (len(api_key) - 4) + api_key[-4:] if len(api_key) > 4 else '****'}")
    print()
    
    # Test connection
    if not test_connection(kibana_url, api_key):
        return False
    
    # Test single monitor export
    if not test_single_monitor_export(kibana_url, api_key):
        return False
    
    # Ask if user wants to run full export
    print("\n" + "=" * 50)
    response = input("🤔 Do you want to run the full export? (y/N): ").strip().lower()
    
    if response in ['y', 'yes']:
        print("\n🏃 Running full export...")
        try:
            exporter = SyntheticsExporter(kibana_url, api_key)
            exporter.export_monitors()
            print("🎉 Full export completed successfully!")
            
            # Show what was created
            monitors_dir = Path('monitors')
            if monitors_dir.exists():
                files = list(monitors_dir.glob('*.json'))
                print(f"📁 Created {len(files)} files in 'monitors' directory:")
                for file in files[:5]:  # Show first 5 files
                    print(f"   - {file.name}")
                if len(files) > 5:
                    print(f"   ... and {len(files) - 5} more files")
            
        except Exception as e:
            print(f"❌ Full export failed: {str(e)}")
            return False
    else:
        print("👍 Skipping full export. Tests completed successfully!")
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)
    print("\n✨ All tests passed!")