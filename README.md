# Synthetics Monitors GitOps

This repository provides a complete GitOps solution for managing Elastic Synthetics monitors with automated workflows for export, import, and Kubernetes deployment.

## Overview

This GitOps solution provides:
- **Export**: Automatically export synthetic monitors from Kibana to Git
- **Import**: Deploy monitor configurations from Git back to Kibana  
- **Multi-Space Support**: Manage monitors across multiple Kibana spaces
- **Location-based Organization**: Monitors organized by space and location
- **Elastic Agent Management**: Automatic Elastic Agent configuration updates
- **Kubernetes Deployment**: Deploy Elastic Agents to Kubernetes clusters
- **Version Control**: Full history and change tracking for all configurations

## Architecture

The system consists of four main workflows:

1. **Export Synthetics** - Exports monitors from Kibana to Git
2. **Import Synthetics** - Imports monitor changes from Git to Kibana
3. **Update Elastic Agent Config** - Updates agent configurations based on monitor changes
4. **Deploy to Kubernetes** - Deploys updated configurations to Kubernetes clusters

## Setup

### 1. Configure GitHub Secrets

Add the following secrets to your GitHub repository:

- `KIBANA_URL`: Your Kibana instance URL (e.g., `https://your-kibana.example.com`)
- `KIBANA_API_KEY`: Your Kibana API key for authentication

### 2. Configure GitHub Variables (Optional)

- `KIBANA_SPACES`: Comma-separated list of Kibana spaces to export (defaults to 'default')

### 3. Vault Configuration (For Kubernetes Deployment)

The Kubernetes deployment workflow uses HashiCorp Vault for secure credential management:
- `VAULT_URL`: Vault instance URL
- `VAULT_ROLE`: Vault role for authentication
- `VAULT_JWT_PATH`: JWT authentication path

## Directory Structure

The repository uses a space and location-based organization:

```
monitors/
├── default/                    # Kibana space: 'default'
│   ├── Asia_Pacific_India/
│   │   ├── monitor-1.json      # Monitor configuration
│   │   └── elastic-agent.yml   # Elastic Agent configuration
│   └── Europe_West/
│       ├── monitor-2.json
│       └── elastic-agent.yml
├── testsynth/                  # Kibana space: 'testsynth'
│   ├── test_loc/
│   │   ├── https___www.youtube.com.json
│   │   └── elastic-agent.yml
│   └── Asia_Pacific_India/
│       └── elastic-agent.yml
└── inputs/                     # Kubernetes deployment configs
    ├── loc1/
    │   ├── agent-deployment.yml
    │   ├── kustomization.yml
    │   └── elastic-agent.yml
    └── loc2/
        ├── agent-deployment.yml
        ├── kustomization.yml
        └── elastic-agent.yml
```

### Benefits of This Structure:
- **Multi-Space Management**: Separate configurations per Kibana space
- **Location Isolation**: Each location has its own folder and agent config
- **Team Ownership**: Different teams can manage different spaces/locations
- **Selective Deployment**: Deploy only specific configurations
- **Clear Organization**: Easy to see which monitors run where

## Workflows

### 1. Export Synthetics Monitors

**File**: `.github/workflows/export-synthetics.yml`

**Triggers**:
- Manual trigger via workflow_dispatch
- After successful import workflows (optional)

**Features**:
- Exports monitors from multiple Kibana spaces
- Organizes monitors by space and location
- Creates location-specific Elastic Agent configurations
- Commits changes automatically

**Usage**:
```bash
# Manual export with specific spaces
# Via GitHub Actions UI, set spaces input: "default,production,staging"

# Local testing
export KIBANA_URL="https://your-kibana.example.com"
export KIBANA_API_KEY="your-api-key"
export KIBANA_SPACES="default,testsynth"
python .github/scripts/export-synthetics-monitors.py
```

### 2. Import Synthetics Monitors

**File**: `.github/workflows/import-synthetics.yml`

**Triggers**:
- Manual trigger with options for dry-run, live import, or fresh import
- Pull requests affecting monitor files
- Push to main branch (auto-import changed files)

**Features**:
- Multi-space support with automatic space detection
- Dry-run mode for validation
- Fresh import mode for new spaces
- Changed-files-only processing for efficiency
- Automatic export of updated configurations

**Usage**:
```bash
# Dry run (preview changes)
export DRY_RUN="true"
python .github/scripts/import-synthetics-monitors.py

# Live import
export DRY_RUN="false"
python .github/scripts/import-synthetics-monitors.py

# Fresh import (for new spaces)
python .github/scripts/import-synthetics-monitors.py --fresh-import

# Import only changed files
export CHANGED_FILES="monitors/default/Asia_Pacific_India/monitor.json"
python .github/scripts/import-synthetics-monitors.py --changed-files
```

### 3. Update Elastic Agent Config

**File**: `.github/workflows/update-elastic-agent-config.yml`

**Triggers**:
- After successful import workflows
- Detects changed monitor folders and updates corresponding agent configs

**Features**:
- Fetches latest agent configurations from Kibana Fleet API
- Updates elastic-agent.yml files for changed locations
- Processes Kubernetes secrets (K8SSEC_ → ${SECRET_NAME})
- Handles both PR updates and new branch creation

**Usage**:
```bash
# Update specific folders
python .github/scripts/update-elastic-agent.py default/Asia_Pacific_India testsynth/test_loc
```

### 4. Deploy to Kubernetes

**File**: `.github/workflows/deploy-kubernetes.yml`

**Triggers**:
- Manual trigger with environment selection (loc1, loc2, or both)
- Push to main branch affecting Kubernetes manifest files
- Changes to: `inputs/*/agent-deployment.yml`, `inputs/*/kustomization.yml`, `inputs/*/elastic-agent.yml`

**Features**:
- Deploys to multiple Kubernetes clusters (loc1, loc2)
- Vault integration for secure credential management
- ConfigMap hash-based pod restarts
- Rollback on failure
- Deployment status tracking

## API Endpoints Used

### Synthetics API
- `GET /s/{space_id}/api/synthetics/monitors` - List monitors in space
- `GET /s/{space_id}/api/synthetics/monitors/{config_id}` - Get monitor details
- `POST /s/{space_id}/api/synthetics/monitors` - Create monitor
- `PUT /s/{space_id}/api/synthetics/monitors/{config_id}` - Update monitor

### Fleet API
- `GET /api/fleet/agent_policies/{policy_id}/download` - Download agent configuration

## Local Testing

### Test Export
```bash
# Windows
test-setup.bat
# Then run: python test-local.py

# Linux/Mac
pip install -r .github/scripts/requirements.txt
export KIBANA_URL="https://your-kibana.example.com"
export KIBANA_API_KEY="your-api-key"
python test-local.py
```

### Test Import
```bash
export KIBANA_URL="https://your-kibana.example.com"
export KIBANA_API_KEY="your-api-key"
export KIBANA_SPACE_ID="default"
python test-import.py
```

## Advanced Features

### Multi-Space Support
The system automatically detects and processes monitors from multiple Kibana spaces:
- Monitors are organized by space in the directory structure
- Each space is processed independently
- Space-specific importers handle authentication and API calls

### Fresh Import Mode
For new Kibana spaces or initial setup:
- Imports all monitors without checking for existing ones
- Skips the export workflow to preserve original Git files
- Useful for migrating monitors to new environments

### Kubernetes Secrets Processing
Elastic Agent configurations support Kubernetes secret references:
- `K8SSEC_SECRET_NAME` → `${SECRET_NAME}`
- `QK8SSEC_SECRET_NAME` → `'${SECRET_NAME}'` (quoted version)

### Location Merging
When the same monitor exists in multiple locations:
- Locations are automatically merged during import
- Each location gets its own file and agent configuration
- Prevents duplicate monitor creation

## Troubleshooting

### Common Issues

1. **Authentication Errors**: Verify Kibana URL and API key
2. **Space Access**: Ensure API key has access to all required spaces
3. **Agent Policy Not Found**: Check that agentPolicyId exists in monitor JSON
4. **Kubernetes Deployment Failures**: Verify Vault credentials and cluster access

### Debugging

- Check GitHub Actions logs for detailed error messages
- Use dry-run mode to validate changes before applying
- Test locally with the provided test scripts
- Enable debug logging in scripts for more verbose output

### File Validation

All monitor JSON files are validated before import:
```bash
# Validate JSON syntax
find monitors -name "*.json" -exec python -m json.tool {} \; > /dev/null
```

## Usage Examples

### Example 1: Initial Setup and Export

**Scenario**: You have an existing Kibana instance with synthetic monitors and want to start managing them with GitOps.

```bash
# 1. Set up environment variables
export KIBANA_URL="https://my-kibana.elastic-cloud.com"
export KIBANA_API_KEY="your-api-key-here"
export KIBANA_SPACES="default,production"

# 2. Test connection first
python test-local.py

# 3. Export all existing monitors
python .github/scripts/export-synthetics-monitors.py
```

**Result**: Creates directory structure with all monitors organized by space and location:
```
monitors/
├── default/
│   ├── US_East/
│   │   ├── website_health_check.json
│   │   └── elastic-agent.yml
│   └── Europe_West/
│       ├── api_endpoint_monitor.json
│       └── elastic-agent.yml
└── production/
    └── Asia_Pacific_India/
        ├── critical_service_monitor.json
        └── elastic-agent.yml
```

### Example 2: Adding a New Monitor

**Scenario**: You want to add a new website monitoring check.

```bash
# 1. Create monitor JSON file in appropriate location
# File: monitors/default/US_East/new_website_monitor.json
```

```json
{
  "type": "http",
  "enabled": true,
  "name": "New Website Monitor",
  "locations": [
    {
      "id": "us-east-1",
      "label": "US East",
      "geo": {
        "lat": 40.7128,
        "lon": -74.0060
      },
      "isServiceManaged": false,
      "agentPolicyId": "fleet-policy-123"
    }
  ],
  "schedule": {
    "unit": "m",
    "number": "5"
  },
  "url": "https://new-website.example.com",
  "max_redirects": 3,
  "timeout": "30s"
}
```

```bash
# 2. Test the import locally (dry run)
export DRY_RUN="true"
python test-import.py

# 3. Commit and push changes
git add monitors/default/US_East/new_website_monitor.json
git commit -m "Add new website monitor for US East"
git push origin main
```

**Result**: The import workflow automatically runs and creates the monitor in Kibana.

### Example 3: Updating Monitor Configuration

**Scenario**: You need to change the monitoring frequency from 5 minutes to 2 minutes.

```bash
# 1. Edit the monitor file
# Change: "number": "5" to "number": "2" in the JSON file

# 2. Create a pull request
git checkout -b update-monitor-frequency
git add monitors/default/US_East/new_website_monitor.json
git commit -m "Update monitoring frequency to 2 minutes"
git push origin update-monitor-frequency

# 3. Create PR via GitHub UI
```

**Result**: 
- PR triggers dry-run import showing preview of changes
- After PR merge, changes are automatically applied to Kibana
- Elastic Agent configurations are updated automatically

### Example 4: Multi-Space Deployment

**Scenario**: You manage monitors across development, staging, and production spaces.

```bash
# 1. Export from all spaces
export KIBANA_SPACES="development,staging,production"
python .github/scripts/export-synthetics-monitors.py
```

**Directory structure**:
```
monitors/
├── development/
│   └── test_location/
│       ├── dev_api_test.json
│       └── elastic-agent.yml
├── staging/
│   └── staging_location/
│       ├── staging_integration_test.json
│       └── elastic-agent.yml
└── production/
    ├── US_East/
    │   ├── prod_website_monitor.json
    │   └── elastic-agent.yml
    └── Europe_West/
        ├── prod_api_monitor.json
        └── elastic-agent.yml
```

```bash
# 2. Import to specific space only
export KIBANA_SPACE_ID="staging"
export DRY_RUN="false"
python .github/scripts/import-synthetics-monitors.py
```

### Example 5: Fresh Import for New Environment

**Scenario**: Setting up monitoring in a new Kibana space or environment.

```bash
# 1. Use fresh import mode (doesn't check for existing monitors)
# Via GitHub Actions UI:
# - Workflow: Import Synthetics Monitors
# - fresh_import: true
# - dry_run: false
# - space_id: new-environment

# 2. Or locally:
export KIBANA_SPACE_ID="new-environment"
export DRY_RUN="false"
export FRESH_IMPORT="true"
python .github/scripts/import-synthetics-monitors.py --fresh-import
```

**Result**: All monitors are created in the new space without checking for existing ones.

### Example 6: Kubernetes Deployment

**Scenario**: Deploy updated Elastic Agent configurations to Kubernetes clusters.

```bash
# 1. Update Kubernetes manifests in inputs/ directory
# File: inputs/loc1/elastic-agent.yml

# 2. Commit changes
git add inputs/loc1/
git commit -m "Update Elastic Agent config for loc1"
git push origin main
```

**Result**: 
- Kubernetes deployment workflow automatically detects changes
- Deploys to loc1 cluster only
- Updates ConfigMap and restarts pods
- Provides deployment status and verification commands

**Manual deployment**:
```bash
# Via GitHub Actions UI:
# - Workflow: Deploy to Kubernetes  
# - environment: loc1 (or loc2, or both)
# - force_deploy: false
```

### Example 7: Troubleshooting Failed Import

**Scenario**: An import fails and you need to debug the issue.

```bash
# 1. Run local dry-run to identify issues
export DRY_RUN="true"
python test-import.py

# 2. Validate JSON files
find monitors -name "*.json" -exec python -m json.tool {} \; > /dev/null

# 3. Check specific monitor file
python -m json.tool monitors/default/US_East/problematic_monitor.json

# 4. Test with single file
export CHANGED_FILES="monitors/default/US_East/problematic_monitor.json"
export DRY_RUN="true"
python .github/scripts/import-synthetics-monitors.py --changed-files
```

### Example 8: Bulk Monitor Updates

**Scenario**: You need to update the schedule for all monitors in a specific location.

```bash
# 1. Use a script to update multiple files
find monitors/default/US_East -name "*.json" -exec sed -i 's/"number": "5"/"number": "3"/g' {} \;

# 2. Verify changes
git diff

# 3. Commit and push
git add monitors/default/US_East/
git commit -m "Update all US East monitors to 3-minute intervals"
git push origin main
```

### Example 9: Environment-Specific Configuration

**Scenario**: Different monitoring configurations for different environments.

**Development** (`monitors/development/test_loc/api_monitor.json`):
```json
{
  "name": "API Monitor - Dev",
  "schedule": {"unit": "m", "number": "10"},
  "url": "https://api-dev.example.com/health",
  "timeout": "10s"
}
```

**Production** (`monitors/production/US_East/api_monitor.json`):
```json
{
  "name": "API Monitor - Prod",
  "schedule": {"unit": "m", "number": "1"},
  "url": "https://api.example.com/health", 
  "timeout": "5s"
}
```

```bash
# Deploy to specific environment
export KIBANA_SPACE_ID="production"
python .github/scripts/import-synthetics-monitors.py
```

### Example 10: Monitoring Workflow Status

**Scenario**: Check the status of your GitOps workflows.

```bash
# 1. Check recent workflow runs via GitHub CLI
gh run list --workflow="Import Synthetics Monitors"

# 2. View specific run details
gh run view <run-id>

# 3. Check deployment status
gh run list --workflow="Deploy to Kubernetes"

# 4. Monitor via GitHub Actions UI
# Go to: https://github.com/your-org/your-repo/actions
```

## Customization

You can customize the workflows by:
- Modifying space lists in environment variables
- Changing file naming conventions in export scripts
- Adding custom validation rules
- Extending Kubernetes deployment logic
- Adding notification integrations