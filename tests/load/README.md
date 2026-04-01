# Project Aura - Load Testing Framework

k6-based load testing framework for validating system performance under production-like conditions.

**Issue:** #13 - Implement load testing framework

## Quick Start

```bash
# Install k6
brew install k6  # macOS
# or: apt install k6  # Linux

# Run smoke test (default)
./tests/load/run-load-tests.sh

# Run stress test on API endpoints
./tests/load/run-load-tests.sh --profile stress --scenario api

# Run against staging
./tests/load/run-load-tests.sh --url https://api.aura.staging
```

## Directory Structure

```
tests/load/
├── README.md              # This file
├── config.js              # Centralized configuration
├── run-load-tests.sh      # Test runner script
├── lib/
│   └── helpers.js         # Shared utilities
├── scenarios/
│   ├── api_endpoints.js   # API endpoint tests
│   ├── database_performance.js  # Neptune/OpenSearch tests
│   └── hitl_workflow.js   # HITL approval workflow tests
└── results/               # Test output (gitignored)
```

## Load Profiles

| Profile | VUs | Duration | Purpose |
|---------|-----|----------|---------|
| smoke | 1 | 30s | Verify tests work |
| average | 10 | 9m | Normal production traffic |
| stress | 10→150 | 19m | Find breaking point |
| spike | 10→200→10 | 4m | Test sudden traffic surge |
| soak | 20 | 40m | Detect memory leaks |

## Test Scenarios

### API Endpoints (`api_endpoints.js`)

Tests core API endpoints:
- Health checks (`/health`, `/health/ready`)
- Job management (`/jobs`, `/jobs/{id}/status`)
- Patch operations (`/patches`)
- Settings (`/settings`)

```bash
k6 run tests/load/scenarios/api_endpoints.js
k6 run -e PROFILE=stress tests/load/scenarios/api_endpoints.js
```

### Database Performance (`database_performance.js`)

Tests Neptune and OpenSearch via API:
- Context retrieval (hybrid query)
- Vector search (semantic)
- Graph queries (structural)
- Hybrid search (combined)

```bash
k6 run tests/load/scenarios/database_performance.js
```

### HITL Workflow (`hitl_workflow.js`)

Tests the approval workflow:
- List pending approvals
- View approval details
- View patch diffs
- Submit decisions

```bash
k6 run tests/load/scenarios/hitl_workflow.js
```

## Performance SLAs

| Operation | p95 Target | p99 Target |
|-----------|-----------|------------|
| Health check | 100ms | 200ms |
| Job operations | 500ms | 1000ms |
| Patch operations | 1000ms | 2000ms |
| HITL approval | 500ms | 1000ms |
| Neptune simple query | 100ms | 200ms |
| Neptune traversal | 500ms | 1000ms |
| OpenSearch vector | 200ms | 500ms |
| OpenSearch hybrid | 500ms | 1000ms |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BASE_URL` | `http://localhost:8000` | API base URL |
| `K6_AUTH_TOKEN` | `test-token...` | Auth token for API |
| `PROFILE` | `smoke` | Load profile |
| `NEPTUNE_ENDPOINT` | `neptune.aura.local:8182` | Neptune endpoint |
| `OPENSEARCH_ENDPOINT` | `opensearch.aura.local:9200` | OpenSearch endpoint |

## CI Integration

Add to your CI pipeline:

```yaml
# GitHub Actions example
load-test:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4

    - name: Install k6
      run: |
        sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
        echo "deb https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
        sudo apt-get update
        sudo apt-get install k6

    - name: Run load tests
      run: ./tests/load/run-load-tests.sh --profile smoke
      env:
        BASE_URL: ${{ secrets.STAGING_API_URL }}
        K6_AUTH_TOKEN: ${{ secrets.LOAD_TEST_TOKEN }}

    - name: Upload results
      uses: actions/upload-artifact@v4
      with:
        name: load-test-results
        path: tests/load/results/
```

## Grafana Integration

Export results to InfluxDB for Grafana dashboards:

```bash
k6 run --out influxdb=http://localhost:8086/k6 tests/load/scenarios/api_endpoints.js
```

## Writing New Scenarios

1. Create a new file in `scenarios/`
2. Import helpers from `../lib/helpers.js`
3. Import config from `../config.js`
4. Define custom metrics using k6/metrics
5. Implement `setup()`, `default`, and `teardown()` functions
6. Add handleSummary for JSON output

Example:

```javascript
import { get, checkResponse } from "../lib/helpers.js";
import { config, getLoadProfile } from "../config.js";

export const options = getLoadProfile("smoke");

export default function() {
  const response = get("/my-endpoint");
  checkResponse(response, "My endpoint");
}
```

## Troubleshooting

### "Connection refused" errors
- Verify the API is running at BASE_URL
- Check firewall/security groups
- Ensure auth token is valid

### High error rates
- Check API logs for errors
- Verify database connections
- Consider reducing VU count

### Slow response times
- Check database query performance
- Monitor CPU/memory usage
- Review application logs

## Results Analysis

Results are saved as JSON in `tests/load/results/`. Key metrics to analyze:

```bash
# View summary
cat tests/load/results/api_endpoints_smoke_*.json | jq '.metrics.http_req_duration'

# Check error rate
cat tests/load/results/api_endpoints_smoke_*.json | jq '.metrics.http_req_failed'
```

CloudWatch Logs Insights query for correlating with load tests:

```sql
fields @timestamp, level, message, extra.duration_ms
| filter correlation_id like /k6-/
| sort @timestamp desc
| limit 100
```
