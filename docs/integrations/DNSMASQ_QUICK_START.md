# dnsmasq Quick Start Guide

## **5-Minute Setup for Project Aura**

---

## Option 1: Kubernetes (Recommended)

Deploy DNS caching to your EKS cluster:

```bash
# 1. Deploy to EKS
kubectl apply -f deploy/kubernetes/dnsmasq-daemonset.yaml

# 2. Verify it's running
kubectl get pods -n aura-network-services

# 3. Test DNS
POD=$(kubectl get pod -n aura-network-services -l app=dnsmasq -o jsonpath='{.items[0].metadata.name}')
kubectl exec -it $POD -n aura-network-services -- nslookup -port=5353 google.com 127.0.0.1

# 4. Update your application to use .aura.local domains
# Example: Change "10.0.3.50:8182" to "neptune.aura.local:8182"
```

**Done!** Your agents now have fast local DNS caching.

---

## Option 2: AWS Fargate (VPC-wide DNS)

Deploy centralized DNS for entire VPC:

```bash
# 1. Run deployment script
./deploy/scripts/deploy-network-services.sh dev 2

# 2. Get DNS endpoint (printed at end of deployment)
# Example: aura-dns-nlb-dev-abc123.elb.us-east-1.amazonaws.com

# 3. Test from EC2 instance in VPC
dig @<nlb-dns-name> neptune.aura.local
```

**Cost:** ~$65/month for dev, ~$185/month for prod

---

## Option 3: Local Development (Podman/Docker)

Test locally before deploying. Per ADR-049, Podman is the primary container runtime.

```bash
# 1. Start dnsmasq (Podman - preferred)
cd deploy/docker/dnsmasq
podman compose up -d dnsmasq-dev

# 2. Test DNS
podman compose exec dns-test-client nslookup -port=5353 google.com dnsmasq-dev

# 3. View logs
podman compose logs -f dnsmasq-dev

# 4. Stop when done
podman compose down
```

**Docker alternative (CI/CD):** Replace `podman compose` with `docker compose`.

**Perfect for:** Local development and testing

---

## Service Discovery Endpoints

After deployment, update your code to use these DNS names:

| Service | Old (IP) | New (DNS) |
|---------|----------|-----------|
| Neptune | 10.0.3.50:8182 | neptune.aura.local:8182 |
| OpenSearch | 10.0.3.60:9200 | opensearch.aura.local:9200 |
| Context Service | 10.0.3.100:8080 | context-retrieval.aura.local:8080 |
| Orchestrator | 10.0.3.102:8080 | orchestrator.aura.local:8080 |

**Python Example:**

```python
# Before
NEPTUNE_ENDPOINT = "10.0.3.50:8182"

# After
NEPTUNE_ENDPOINT = os.environ.get("NEPTUNE_ENDPOINT", "neptune.aura.local:8182")
```

---

## Troubleshooting

**DNS not resolving?**

```bash
# Check dnsmasq is running
kubectl get pods -n aura-network-services  # Kubernetes
aws ecs list-tasks --cluster aura-network-services-dev  # Fargate

# Check logs
kubectl logs -n aura-network-services -l app=dnsmasq --tail=50  # Kubernetes
aws logs tail /aws/ecs/aura-network-services-dev --follow  # Fargate
```

**Need to update DNS entries?**

```bash
# Edit configuration
kubectl edit configmap dnsmasq-config -n aura-network-services

# Restart to apply
kubectl rollout restart daemonset/dnsmasq -n aura-network-services
```

---

## Documentation

- **Full Guide:** `docs/dnsmasq_integration.md` (1,500 lines)
- **Summary:** `DNSMASQ_INTEGRATION_SUMMARY.md` (400 lines)
- **This Guide:** `DNSMASQ_QUICK_START.md` (you are here)

---

## Next Steps

1. ✅ Deploy to dev/qa environment
2. ✅ Test DNS resolution from agents
3. ✅ Update application configs to use .aura.local
4. ✅ Monitor logs for issues
5. ✅ Promote to production

**Questions?** Check `docs/dnsmasq_integration.md` or contact the team.
