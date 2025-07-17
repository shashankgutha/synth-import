# Synthetics Monitors GitOps

This repository contains a complete GitOps workflow for managing synthetic monitors with Kibana using the Synthetics API.

## Overview

This GitOps solution provides:
- **Export**: Automatically export all synthetic monitors from Kibana to Git
- **Import**: Deploy monitor configurations from Git back to Kibana
- **Location-based Organization**: Monitors organized by location for regional management
- **Version Control**: Full history and change tracking for all monitor configurations

## Setup

### 1. Configure GitHub Secrets

Add the following secrets to your GitHub repository:

- `KIBANA_URL`: Your Kibana instance URL (e.g., `https://your-kibana.example.com`)
- `KIBANA_API_KEY`: Your Kibana API key for authentication

### 2. Workflow Configuration

The GitHub Actions workflow (`.github/workflows/export-synthetics.yml`) is configured to:

- Run daily at 2 AM UTC
- Allow manual triggering via workflow_dispatch
- Trigger on changes to the export script or workflow file

## Usage

### Export Monitors (Kibana → Git)

#### Manual Export
```bash
# Install dependencies
pip install requests

# Set environment variables
export KIBANA_URL="https://your-kibana.example.com"
export KIBANA_API_KEY="your-api-key"

# Run the export
python .github/scripts/export-synthetics-monitors.py
```

#### Automated Export
The export workflow runs automatically and will:
1. Export all monitors from Kibana
2. Organize monitors by location in separate folders
3. Commit changes if any monitors were updated
4. Optionally create pull requests for scheduled runs

### Import Monitors (Git → Kibana)

#### Manual Import
```bash
# Set environment variables
export KIBANA_URL="https://your-kibana.example.com"
export KIBANA_API_KEY="your-api-key"
export KIBANA_SPACE_ID="default"  # Optional, defaults to 'default'

# Test import (dry run)
export DRY_RUN="true"
python .github/scripts/import-synthetics-monitors.py

# Live import (applies changes)
export DRY_RUN="false"
python .github/scripts/import-synthetics-monitors.py
```

#### Automated Import
- **Dry Run**: Automatically runs on pushes to main branch (preview mode)
- **Live Import**: Manual trigger via GitHub Actions with option to choose dry-run or live mode
- **Validation**: All JSON files are validated before import

#### Import Workflow Triggers
1. **Push to main**: Runs dry-run validation
2. **Manual trigger**: Choose between dry-run or live import
3. **Monitor file changes**: Validates and previews changes

## Directory Structure

The location-based organization provides clean separation:

```
monitors/
├── Asia_Pacific_India/
│   ├── monitor-1.json          # Monitor config for this location only
│   └── monitor-2.json
├── Europe_West/
│   ├── monitor-1.json          # Same monitor, different location
│   └── monitor-3.json
└── US_East/
    └── monitor-4.json
```

### Benefits of Location-Based Structure:
- **Regional Management**: Deploy monitors to specific locations
- **Team Ownership**: Different teams can manage different regions
- **Selective Deployment**: Import only specific location configurations
- **Clear Organization**: Easy to see which monitors run where

## API Endpoints Used

### Export (Read Operations)
- `GET /api/synthetics/monitors` - List all monitors (paginated, 50 per page)
- `GET /api/synthetics/monitors/{config_id}` - Get detailed monitor configuration

### Import (Write Operations)
- `POST /s/{space_id}/api/synthetics/monitors` - Create a new monitor
- `PUT /s/{space_id}/api/synthetics/monitors/{config_id}` - Update existing monitor

### Field Filtering Rules
**Creating monitors** (removes these fields):
- `id`, `config_id`, `created_at`, `updated_at`, `spaceId`, `url`, `revision`

**Updating monitors** (removes these fields):
- `id`, `config_id`, `created_at`, `updated_at`, `revision`, `spaceId`

## Customization

You can modify the export script to:

- Change the output directory
- Filter specific monitors
- Modify the file naming convention
- Add additional metadata or processing

## Troubleshooting

### Common Issues

1. **Authentication Errors**: Verify your Kibana credentials and URL
2. **API Access**: Ensure your user has permissions to access the Synthetics API
3. **Network Issues**: Check if your Kibana instance is accessible from GitHub Actions

### Debugging

Enable debug logging by modifying the script or checking the GitHub Actions logs for detailed error messages.