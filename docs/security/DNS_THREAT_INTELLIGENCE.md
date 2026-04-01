# DNS Threat Intelligence Integration

This document describes Project Aura's DNS-based threat intelligence integration, which provides automated blocking of malicious domains based on real-time threat feeds.

## Overview

The DNS threat intelligence system integrates with the dnsmasq DNS infrastructure to provide:

- **Automated Blocklists**: Daily updates from multiple threat intelligence sources
- **Multi-Source Aggregation**: NVD, CISA KEV, GitHub Advisories, URLhaus, Abuse.ch
- **Zero-Downtime Updates**: Hot-reload configuration without service interruption
- **Comprehensive Logging**: Audit trails for compliance (CMMC, SOX, NIST 800-53)

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         Threat Intelligence Pipeline                      │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐  │
│  │     NVD     │   │  CISA KEV   │   │   URLhaus   │   │  Abuse.ch   │  │
│  │   CVE API   │   │  Catalog    │   │   Malware   │   │   Feodo     │  │
│  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘  │
│         │                 │                 │                 │          │
│         └────────┬────────┴────────┬────────┴────────┬────────┘          │
│                  │                 │                 │                   │
│                  ▼                 ▼                 ▼                   │
│         ┌────────────────────────────────────────────────┐              │
│         │          DNS Blocklist Service                 │              │
│         │  (src/services/dns_blocklist_service.py)       │              │
│         └─────────────────────┬──────────────────────────┘              │
│                               │                                          │
│                               ▼                                          │
│         ┌────────────────────────────────────────────────┐              │
│         │       dnsmasq Configuration Generator          │              │
│         │    (address=/malware.com/0.0.0.0 format)       │              │
│         └─────────────────────┬──────────────────────────┘              │
│                               │                                          │
│               ┌───────────────┼───────────────┐                         │
│               ▼               ▼               ▼                         │
│        ┌────────────┐  ┌────────────┐  ┌────────────┐                   │
│        │     S3     │  │ ConfigMap  │  │   Local    │                   │
│        │   Bucket   │  │(Kubernetes)│  │   File     │                   │
│        └──────┬─────┘  └──────┬─────┘  └────────────┘                   │
│               │               │                                          │
│               ▼               ▼                                          │
│        ┌────────────┐  ┌────────────┐                                   │
│        │  Tier 2    │  │  Tier 1    │                                   │
│        │  (Fargate) │  │  (EKS)     │                                   │
│        │  dnsmasq   │  │  dnsmasq   │                                   │
│        └────────────┘  └────────────┘                                   │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

## Threat Intelligence Sources

### 1. NVD (National Vulnerability Database)

- **API**: CVE 2.0 REST API
- **Data**: CVE records with CVSS scores and references
- **Update Frequency**: Real-time
- **Rate Limits**: 5 req/30s (without API key), 50 req/30s (with key)

### 2. CISA KEV (Known Exploited Vulnerabilities)

- **Feed**: JSON catalog of actively exploited vulnerabilities
- **Data**: CVE IDs, remediation deadlines, ransomware indicators
- **Update Frequency**: Daily
- **Priority**: Critical - all KEV entries are actively exploited

### 3. GitHub Security Advisories

- **API**: GitHub Advisory Database API
- **Data**: Package ecosystem vulnerabilities (pip, npm, go)
- **Ecosystems**: Python, JavaScript, Go, Ruby, Rust
- **Update Frequency**: Real-time

### 4. URLhaus (Abuse.ch)

- **Feed**: Malware distribution URLs
- **Data**: Domains hosting malware payloads
- **Update Frequency**: Real-time
- **Category**: Malware distribution

### 5. Feodo Tracker (Abuse.ch)

- **Feed**: C2 domain blocklist
- **Data**: Command & Control server domains
- **Update Frequency**: Daily
- **Category**: Botnet C2 infrastructure

## Components

### DNSBlocklistService

The core service that aggregates threat intelligence and generates blocklists.

**Location**: `src/services/dns_blocklist_service.py`

**Key Features**:
- Multi-source threat aggregation
- Domain validation and deduplication
- Whitelist support (prevent false positives)
- Severity-based filtering
- dnsmasq configuration generation

**Usage**:

```python
from src.services.dns_blocklist_service import create_blocklist_service, BlocklistConfig

# Create service with custom configuration
config = BlocklistConfig(
    enable_nvd=True,
    enable_cisa_kev=True,
    enable_urlhaus=True,
    enable_abuse_ch=True,
    min_severity="medium",
    block_ransomware=True,
    max_entries=10000,
)

service = create_blocklist_service(config=config)

# Generate blocklist
entries = await service.generate_blocklist()

# Render dnsmasq configuration
dnsmasq_config = service.render_dnsmasq_config(entries)

# Get statistics
stats = service.get_stats()
print(f"Blocked domains: {stats['total_entries']}")
```

### Lambda Function

Automated blocklist updates triggered by CloudWatch Events.

**Location**: `src/lambda/dns_blocklist_updater.py`

**Trigger**: Daily at 6 AM UTC (CloudWatch Events rule)

**Actions**:
1. Fetch threat intelligence from all sources
2. Generate dnsmasq blocklist configuration
3. Upload to S3 for ECS Fargate (Tier 2)
4. Stage for Kubernetes ConfigMap sync (Tier 1)
5. Send SNS notification with update summary

### Kubernetes CronJob

Syncs blocklist from S3 to Kubernetes ConfigMap.

**Location**: `deploy/kubernetes/dnsmasq-blocklist-sync.yaml`

**Schedule**: Daily at 7 AM UTC (1 hour after Lambda)

**Actions**:
1. Download blocklist from S3
2. Update `dnsmasq-blocklist` ConfigMap
3. Annotate DaemonSet to trigger reload

### Manual Update Script

For on-demand blocklist updates.

**Location**: `deploy/scripts/update-dnsmasq-blocklist.sh`

**Usage**:

```bash
# Dry run (generate but don't deploy)
./update-dnsmasq-blocklist.sh -e dev --dry-run

# Update S3 and Kubernetes
./update-dnsmasq-blocklist.sh -e dev -s -k

# Generate local file only
./update-dnsmasq-blocklist.sh --local-only
```

## Threat Categories

| Category | Description | Severity |
|----------|-------------|----------|
| MALWARE | Generic malware distribution | High |
| PHISHING | Credential harvesting sites | High |
| C2_COMMAND_CONTROL | Botnet command servers | Critical |
| CRYPTOMINER | Cryptocurrency mining malware | Medium |
| RANSOMWARE | Ransomware distribution | Critical |
| BOTNET | Botnet infrastructure | High |
| SPAM | Spam distribution | Low |
| ADWARE | Advertising malware | Low |

## Configuration

### BlocklistConfig Options

| Option | Default | Description |
|--------|---------|-------------|
| `enable_nvd` | `True` | Fetch from NVD CVE database |
| `enable_cisa_kev` | `True` | Fetch CISA KEV catalog |
| `enable_github` | `True` | Fetch GitHub Security Advisories |
| `enable_urlhaus` | `True` | Fetch URLhaus malware URLs |
| `enable_abuse_ch` | `True` | Fetch Abuse.ch Feodo Tracker |
| `min_severity` | `"medium"` | Minimum severity to block |
| `block_ransomware` | `True` | Always block ransomware |
| `max_entries` | `10000` | Maximum blocklist size |
| `include_comments` | `True` | Include metadata comments |

### Whitelist

Default whitelisted domains (never blocked):
- Critical infrastructure: `google.com`, `amazonaws.com`, `microsoft.com`
- Project Aura: `aura.local`, `aenealabs.com`
- CDNs: `cloudflare.com`, `akamai.com`, `fastly.com`

Custom whitelist file: Set `whitelist_file` in BlocklistConfig

### Custom Blocklist

Add custom domains via file:

```
# custom-blocklist.csv
# domain,category,severity,notes
evil.com,malware,critical,Internal threat intel
phishing.net,phishing,high,Reported by security team
```

Set `custom_blocklist_file` in BlocklistConfig.

## Deployment

### Prerequisites

1. dnsmasq Tier 1 (EKS DaemonSet) or Tier 2 (ECS Fargate) deployed
2. S3 bucket for configuration storage
3. IAM roles with appropriate permissions
4. SNS topic for notifications (optional)

### Deploy Blocklist Sync CronJob

```bash
kubectl apply -f deploy/kubernetes/dnsmasq-blocklist-sync.yaml
```

### Manual Trigger

```bash
# Create ad-hoc job from CronJob template
kubectl create job --from=cronjob/blocklist-sync manual-sync -n aura-network-services
```

### Verify Blocklist

```bash
# Check ConfigMap
kubectl get configmap dnsmasq-blocklist -n aura-network-services -o yaml

# Check blocklist entries
kubectl get configmap dnsmasq-blocklist -n aura-network-services -o jsonpath='{.data.blocklist\.conf}' | grep '^address=' | wc -l
```

## Monitoring

### CloudWatch Metrics

- `BlocklistTotalEntries`: Total blocked domains
- `BlocklistUpdateSuccess`: Successful update count
- `BlocklistUpdateFailure`: Failed update count
- `BlocklistUpdateDuration`: Update processing time

### CloudWatch Alarms

- High failure rate: >3 consecutive update failures
- Blocklist size anomaly: Sudden increase/decrease in entries

### Logs

- Lambda logs: `/aws/lambda/aura-blocklist-updater-dev`
- CronJob logs: `kubectl logs -l app.kubernetes.io/name=blocklist-sync -n aura-network-services`

## Security Considerations

### Feed Validation

- All feeds are fetched over HTTPS
- Response validation before processing
- Size limits to prevent DoS
- Graceful fallback on API failures

### False Positive Prevention

- Default whitelist for critical infrastructure
- Custom whitelist support
- Severity-based filtering
- Audit logging for blocked domains

### Compliance

- Full audit trail of blocklist updates
- Timestamped configuration with hash
- Notification on every update
- Supports CMMC, SOX, NIST 800-53 requirements

## Testing

Run blocklist service tests:

```bash
pytest tests/test_dns_blocklist_service.py -v
```

Test coverage:
- 25 unit tests
- BlocklistEntry generation
- Domain validation and whitelisting
- Severity filtering
- dnsmasq configuration rendering
- Statistics tracking

## Troubleshooting

### Blocklist Not Updating

1. Check Lambda execution logs
2. Verify S3 bucket permissions
3. Check CronJob status: `kubectl get cronjobs -n aura-network-services`
4. Verify IAM role has S3 and ConfigMap permissions

### False Positives

1. Add domain to whitelist file
2. Run manual update: `./update-dnsmasq-blocklist.sh -e dev -k`
3. Verify removal: Check ConfigMap

### High Memory Usage

1. Reduce `max_entries` in BlocklistConfig
2. Disable unused sources (e.g., `enable_github=False`)
3. Increase severity threshold (`min_severity="high"`)

## Related Documentation

- [dnsmasq Integration Guide](DNSMASQ_INTEGRATION.md)
- [dnsmasq Quick Start](../DNSMASQ_QUICK_START.md)
- [Network Services Architecture](HITL_SANDBOX_ARCHITECTURE.md)
