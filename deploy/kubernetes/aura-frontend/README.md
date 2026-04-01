# Project Aura - Frontend Kubernetes Deployment

React dashboard for HITL approval workflow, served via nginx.

## Architecture

```
Browser → aura-frontend (nginx:8080) → /api/* proxy → aura-api:8000
                                     → /* static files
```

## Prerequisites

1. ECR repository created: `aura-frontend-dev`
2. Docker image pushed to ECR
3. aura-api service running in cluster

## Deploy

```bash
# Build and push Docker image
docker build --platform linux/amd64 \
  -t 123456789012.dkr.ecr.us-east-1.amazonaws.com/aura-frontend-dev:latest \
  -f deploy/docker/frontend/Dockerfile.frontend .

aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com

docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/aura-frontend-dev:latest

# Deploy to EKS
kubectl apply -k deploy/kubernetes/aura-frontend/

# Verify
kubectl get pods -l app=aura-frontend
kubectl get svc aura-frontend
```

## Port Forward for Local Access

```bash
kubectl port-forward svc/aura-frontend 3000:80
# Open http://localhost:3000/approvals
```

## Routes

| Path | Description |
|------|-------------|
| `/` | Dashboard home |
| `/projects` | Code knowledge explorer |
| `/approvals` | HITL approval workflow |
| `/api/*` | Proxied to aura-api backend |
| `/health` | Nginx health check |
