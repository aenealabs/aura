#!/bin/bash
# =============================================================================
# Generate API Documentation Script
# =============================================================================
# Generates static API documentation from FastAPI's OpenAPI spec.
#
# Features:
# - Extracts OpenAPI spec from running FastAPI app
# - Generates static ReDoc HTML
# - Creates downloadable OpenAPI spec files (JSON and YAML)
# - Optionally deploys to S3 bucket
#
# Usage:
#   ./generate-api-docs.sh                    # Generate only
#   ./generate-api-docs.sh --deploy dev       # Generate and deploy to dev
#   ./generate-api-docs.sh --deploy prod      # Generate and deploy to prod
#
# Prerequisites:
# - Python 3.11+ with fastapi, pydantic
# - Node.js for redoc-cli (optional, falls back to CDN version)
# - AWS CLI configured (for deployment)
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUTPUT_DIR="$PROJECT_ROOT/docs-portal/build"
DEPLOY_ENV=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --deploy)
            DEPLOY_ENV="$2"
            shift 2
            ;;
        --output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "==================================================="
echo "Project Aura - API Documentation Generator"
echo "==================================================="
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Step 1: Extract OpenAPI spec from FastAPI
echo "[1/4] Extracting OpenAPI spec..."

cd "$PROJECT_ROOT"

# Create a temporary Python script to extract the OpenAPI spec
cat > /tmp/extract_openapi.py << 'PYEOF'
import json
import yaml
import sys
sys.path.insert(0, '.')

from src.api.main import app

# Get OpenAPI schema
openapi_schema = app.openapi()

# Enhance schema for documentation
openapi_schema["info"]["x-logo"] = {
    "url": "https://aenealabs.com/logo.svg",
    "altText": "Aenea Labs"
}

openapi_schema["info"]["description"] = """
# Project Aura API

Autonomous security remediation platform API for vulnerability detection,
patch generation, and human-in-the-loop approval workflows.

## Authentication

All API endpoints require authentication using JWT Bearer tokens.
Obtain a token by authenticating via the `/api/v1/auth/login` endpoint.

```bash
curl -X POST https://api.aenealabs.com/api/v1/auth/login \\
  -H "Content-Type: application/json" \\
  -d '{"email": "user@example.com", "password": "..."}'
```

## Rate Limits

- Standard tier: 1,000 requests/hour
- Professional tier: 10,000 requests/hour
- Enterprise tier: Unlimited

## Support

For API support, contact api-support@aenealabs.com or visit
[Aenea Labs Support](https://aenealabs.com/support).
"""

# Output paths from command line
output_dir = sys.argv[1] if len(sys.argv) > 1 else "docs-portal/build"

# Write JSON
with open(f"{output_dir}/openapi.json", "w") as f:
    json.dump(openapi_schema, f, indent=2)

# Write YAML
with open(f"{output_dir}/openapi.yaml", "w") as f:
    yaml.dump(openapi_schema, f, default_flow_style=False, sort_keys=False)

print(f"OpenAPI spec written to {output_dir}/")
PYEOF

python3 /tmp/extract_openapi.py "$OUTPUT_DIR" 2>/dev/null || {
    echo "Warning: Could not extract live OpenAPI spec"
    echo "Creating placeholder spec..."
    cat > "$OUTPUT_DIR/openapi.json" << 'SPECEOF'
{
  "openapi": "3.1.0",
  "info": {
    "title": "Project Aura API",
    "version": "1.0.0",
    "description": "Autonomous security remediation platform API",
    "x-logo": {
      "url": "https://aenealabs.com/logo.svg"
    }
  },
  "servers": [
    {"url": "https://api.aenealabs.com", "description": "Production"},
    {"url": "https://api-dev.aenealabs.com", "description": "Development"}
  ],
  "paths": {}
}
SPECEOF
}

echo "  ✓ OpenAPI spec extracted"

# Step 2: Generate ReDoc HTML
echo "[2/4] Generating ReDoc documentation..."

# Check if redoc-cli is available
if command -v npx &> /dev/null && npx redoc-cli --version &> /dev/null 2>&1; then
    echo "  Using redoc-cli..."
    npx redoc-cli build "$OUTPUT_DIR/openapi.json" \
        --output "$OUTPUT_DIR/index.html" \
        --title "Project Aura API" \
        --options.theme.colors.primary.main="#3B82F6" \
        --options.hideDownloadButton=false \
        --options.nativeScrollbars=true
else
    echo "  Using CDN-based ReDoc..."
    cat > "$OUTPUT_DIR/index.html" << 'HTMLEOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Project Aura API Documentation</title>
    <meta name="description" content="API reference for Project Aura autonomous security remediation platform">
    <link rel="icon" type="image/svg+xml" href="https://aenealabs.com/favicon.svg">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono&display=swap" rel="stylesheet">
    <style>
        body {
            margin: 0;
            padding: 0;
        }
        .custom-header {
            background: linear-gradient(to right, #1e3a5f, #3B82F6);
            color: white;
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .custom-header h1 {
            margin: 0;
            font-size: 1.5rem;
            font-weight: 600;
            font-family: 'Inter', sans-serif;
        }
        .header-links a {
            color: white;
            text-decoration: none;
            margin-left: 1.5rem;
            font-family: 'Inter', sans-serif;
            font-size: 0.875rem;
        }
        .header-links a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="custom-header">
        <h1>Project Aura API</h1>
        <div class="header-links">
            <a href="https://aenealabs.com">Home</a>
            <a href="https://app.aenealabs.com">Dashboard</a>
            <a href="openapi.json" download>OpenAPI Spec (JSON)</a>
            <a href="openapi.yaml" download>OpenAPI Spec (YAML)</a>
        </div>
    </div>
    <redoc spec-url='openapi.json'
           hide-download-button="false"
           native-scrollbars="true"
           theme='{
               "colors": {
                   "primary": {"main": "#3B82F6"}
               },
               "typography": {
                   "fontFamily": "Inter, sans-serif",
                   "code": {"fontFamily": "JetBrains Mono, monospace"}
               },
               "sidebar": {
                   "backgroundColor": "#f8fafc"
               }
           }'>
    </redoc>
    <script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"></script>
</body>
</html>
HTMLEOF
fi

echo "  ✓ ReDoc documentation generated"

# Step 3: Create 404 page
echo "[3/4] Creating additional pages..."

cat > "$OUTPUT_DIR/404.html" << 'HTML404'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Page Not Found - Project Aura API</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Inter', sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: #f8fafc;
        }
        .container {
            text-align: center;
            padding: 2rem;
        }
        h1 {
            font-size: 6rem;
            color: #3B82F6;
            margin: 0;
        }
        h2 {
            color: #1e293b;
            margin: 1rem 0;
        }
        p {
            color: #64748b;
            margin-bottom: 2rem;
        }
        a {
            display: inline-block;
            background: #3B82F6;
            color: white;
            padding: 0.75rem 1.5rem;
            border-radius: 0.5rem;
            text-decoration: none;
            font-weight: 500;
        }
        a:hover {
            background: #2563eb;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>404</h1>
        <h2>Page Not Found</h2>
        <p>The documentation page you're looking for doesn't exist.</p>
        <a href="/">Back to API Docs</a>
    </div>
</body>
</html>
HTML404

echo "  ✓ Additional pages created"

# Step 4: Deploy to S3 (if requested)
if [ -n "$DEPLOY_ENV" ]; then
    echo "[4/4] Deploying to S3 ($DEPLOY_ENV)..."

    # Get bucket name from CloudFormation exports
    BUCKET_NAME=$(aws cloudformation list-exports \
        --query "Exports[?Name=='aura-docs-bucket-${DEPLOY_ENV}'].Value" \
        --output text 2>/dev/null)

    if [ -z "$BUCKET_NAME" ] || [ "$BUCKET_NAME" == "None" ]; then
        echo "  Warning: Could not find docs bucket for $DEPLOY_ENV"
        echo "  Using default naming convention..."
        ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
        BUCKET_NAME="aura-docs-${ACCOUNT_ID}-${DEPLOY_ENV}"
    fi

    echo "  Uploading to s3://${BUCKET_NAME}/"

    # Sync files to S3
    aws s3 sync "$OUTPUT_DIR" "s3://${BUCKET_NAME}/" \
        --delete \
        --cache-control "max-age=3600" \
        --exclude "*.html" \
        --exclude "openapi.*"

    # Upload HTML with shorter cache
    aws s3 sync "$OUTPUT_DIR" "s3://${BUCKET_NAME}/" \
        --exclude "*" \
        --include "*.html" \
        --cache-control "max-age=300"

    # Upload OpenAPI specs with no-cache for freshness
    aws s3 sync "$OUTPUT_DIR" "s3://${BUCKET_NAME}/" \
        --exclude "*" \
        --include "openapi.*" \
        --cache-control "no-cache, no-store, must-revalidate"

    # Get CloudFront distribution ID
    CF_DIST_ID=$(aws cloudformation list-exports \
        --query "Exports[?Name=='aura-docs-cf-id-${DEPLOY_ENV}'].Value" \
        --output text 2>/dev/null)

    if [ -n "$CF_DIST_ID" ] && [ "$CF_DIST_ID" != "None" ]; then
        echo "  Invalidating CloudFront cache..."
        aws cloudfront create-invalidation \
            --distribution-id "$CF_DIST_ID" \
            --paths "/*" \
            --query 'Invalidation.Id' \
            --output text
    fi

    echo "  ✓ Deployed to $DEPLOY_ENV"
else
    echo "[4/4] Skipping deployment (use --deploy <env> to deploy)"
fi

echo ""
echo "==================================================="
echo "Documentation generated successfully!"
echo "==================================================="
echo ""
echo "Output: $OUTPUT_DIR/"
echo "  - index.html     (ReDoc documentation)"
echo "  - openapi.json   (OpenAPI 3.1 spec)"
echo "  - openapi.yaml   (OpenAPI 3.1 spec)"
echo "  - 404.html       (Error page)"
echo ""

if [ -n "$DEPLOY_ENV" ]; then
    DOCS_URL=$(aws cloudformation list-exports \
        --query "Exports[?Name=='aura-docs-url-${DEPLOY_ENV}'].Value" \
        --output text 2>/dev/null)

    if [ -n "$DOCS_URL" ] && [ "$DOCS_URL" != "None" ]; then
        echo "Live at: $DOCS_URL"
    fi
fi
