# Project Aura Frontend UI - Local Development Runbook

**Version:** 1.0
**Last Updated:** December 8, 2025
**Audience:** Developers, Designers, Product Managers

---

## Overview

Project Aura's frontend is a React-based dashboard providing a user interface for:
- **HITL Approval Workflow** - Human-in-the-loop patch approval
- **Code Knowledge Graph Explorer** - Interactive GraphRAG visualization
- **Agent Orchestration Dashboard** - Monitor and manage AI agents
- **Red Team Dashboard** - Security testing and vulnerability analysis
- **Incident Investigations** - Runtime incident response tracking
- **Integration Hub** - External service connections

**Tech Stack:**
- React 18.3.1
- Vite 6.0.3 (build tool + dev server)
- Tailwind CSS 3.4.16
- React Router 7.1.0
- Heroicons 2.2.0

---

## Prerequisites

Before starting, ensure you have the following installed:

| Tool | Version | Check Command | Install Command |
|------|---------|---------------|-----------------|
| **Node.js** | 18.x or 20.x | `node --version` | https://nodejs.org/ |
| **npm** | 9.x or 10.x | `npm --version` | Included with Node.js |
| **Git** | 2.x+ | `git --version` | https://git-scm.com/ |

Optional (for full-stack development):
| Tool | Version | Purpose |
|------|---------|---------|
| **Python** | 3.11+ | FastAPI backend |
| **AWS CLI** | 2.x | Backend AWS services |

---

## Step 1: Clone Repository (If Not Already Cloned)

```bash
# Clone the repository
git clone https://github.com/aenealabs/aura.git

# Navigate to the repository
cd aura
```

---

## Step 2: Install Frontend Dependencies

```bash
# Navigate to frontend directory
cd frontend

# Install npm packages (this will take 1-2 minutes)
npm install
```

**Expected Output:**
```
added 282 packages, and audited 283 packages in 45s
```

**Troubleshooting:**
- If you see `EACCES` permission errors, avoid using `sudo`. Instead, configure npm to use a local directory: https://docs.npmjs.com/resolving-eacces-permissions-errors
- If packages fail to install, delete `node_modules` and `package-lock.json`, then run `npm install` again

---

## Step 3: Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env.local

# Edit .env.local with your preferred text editor
nano .env.local
```

**Recommended Configuration for Local Development:**

```bash
# API URL - Use Vite proxy for local development
VITE_API_URL=/api/v1

# Your email for approval actions
VITE_REVIEWER_EMAIL=your-email@aenealabs.com
```

**Configuration Options:**

| Environment | VITE_API_URL | Purpose |
|-------------|--------------|---------|
| **Local Dev (Proxy)** | `/api/v1` | Vite proxies to `localhost:8000` |
| **Local Dev (Direct)** | `http://localhost:8000/api/v1` | Direct backend connection |
| **Production** | `https://api.aura.aenealabs.com/api/v1` | EKS deployment |

---

## Step 4: Start the Development Server

```bash
# From the frontend directory
npm run dev
```

**Expected Output:**
```
VITE v6.0.3  ready in 342 ms

➜  Local:   http://localhost:5173/
➜  Network: use --host to expose
➜  press h + enter to show help
```

**Access the UI:**
Open your browser to: **http://localhost:5173/**

---

## Available UI Pages & Components

### Main Routes

| Route | Component | Description |
|-------|-----------|-------------|
| `/` | Dashboard | Overview metrics, system health, agent status |
| `/projects` | CKGEConsole | Code Knowledge Graph Explorer (GraphRAG visualization) |
| `/approvals` | ApprovalDashboard | **HITL patch approval workflow** |
| `/agents` | AgentRegistry | Agent management and orchestration |
| `/incidents` | IncidentInvestigations | Runtime incident response tracking |
| `/red-team` | RedTeamDashboard | Security testing and penetration testing |
| `/integrations` | IntegrationHub | External service connections (GitHub, JIRA, etc.) |
| `/settings` | SettingsPage | User preferences and system configuration |

### Component Inventory

| Component | Purpose |
|-----------|---------|
| `ApprovalDashboard.jsx` | HITL patch approval interface with diff viewer |
| `Dashboard.jsx` | Main overview dashboard with metrics |
| `CKGEConsole.jsx` | Code Knowledge Graph Explorer (GraphRAG) |
| `AgentRegistry.jsx` | Agent lifecycle management |
| `IncidentInvestigations.jsx` | Incident response and RCA tracking |
| `RedTeamDashboard.jsx` | Adversarial testing and security analysis |
| `IntegrationHub.jsx` | External integrations (GitHub, JIRA, Slack) |
| `QueryDecompositionPanel.jsx` | GraphRAG query analysis |
| `Task_Selection.jsx` | Task management interface |
| `SettingsPage.jsx` | User settings and configuration |
| `LoginPage.jsx` | Authentication page |
| `CollapsibleSidebar.jsx` | Navigation sidebar |
| `UserMenu.jsx` | User profile and logout |

---

## Step 5: Viewing Specific UI Components

### Option A: Frontend Only (Mock Data Mode)

If you just want to see the UI without a running backend:

```bash
# The frontend will work with mock data
# Just run the dev server
npm run dev
```

**Available Pages:**
- **Dashboard** → http://localhost:5173/
- **Approvals** → http://localhost:5173/approvals
- **Agents** → http://localhost:5173/agents
- **Red Team** → http://localhost:5173/red-team

### Option B: Full-Stack Development (Live API)

To see real data from the backend API:

#### Terminal 1: Start FastAPI Backend

```bash
# From project root
cd /path/to/project-aura

# Activate virtual environment (if using one)
source venv/bin/activate  # or your venv path

# Install Python dependencies
pip install -r requirements.txt

# Start FastAPI server
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

**Expected Output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12345] using StatReload
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

#### Terminal 2: Start Frontend

```bash
# From frontend directory
cd frontend
npm run dev
```

**Backend API Endpoints:**
- Swagger Docs: http://localhost:8000/docs
- Approval API: http://localhost:8000/api/v1/approvals
- Health Check: http://localhost:8000/health

---

## Step 6: Testing the HITL Approval Dashboard

The HITL Approval Dashboard is the most complete UI component. To test it:

### 1. Navigate to Approvals Page
Open: http://localhost:5173/approvals

### 2. View Approval Requests
The dashboard displays:
- **Pending Approvals** (requiring action)
- **Patch Details** (vulnerability, severity, affected files)
- **Diff Viewer** (side-by-side code comparison)
- **Approval Actions** (Approve, Reject, Request Changes)

### 3. Interact with Approvals
- **View Details** - Click on any approval card
- **Review Diff** - See code changes with syntax highlighting
- **Approve** - Click "Approve" button (requires comment)
- **Reject** - Click "Reject" button (requires reason)

**Mock Data:**
If the backend is not running, the UI will show sample approval requests for demonstration purposes.

---

## UI Design System

Project Aura follows an Apple-inspired minimalist design system:

### Color Palette

| Purpose | Color | Hex Code | Usage |
|---------|-------|----------|-------|
| **Primary** | Blue | `#3B82F6` | Buttons, links, focus states |
| **Critical** | Red | `#DC2626` | Errors, HIGH/CRITICAL severity |
| **Warning** | Orange | `#EA580C` | Warnings, HIGH severity |
| **Success** | Green | `#10B981` | Success states, approved patches |
| **Info** | Blue | `#3B82F6` | Informational messages |
| **Gray** | Neutral | `#6B7280` | Text, borders, backgrounds |

### Typography

| Element | Font | Size | Weight |
|---------|------|------|--------|
| **H1** | Inter | 32px | 700 |
| **H2** | Inter | 24px | 600 |
| **H3** | Inter | 20px | 600 |
| **Body** | Inter | 14px | 400 |
| **Code** | JetBrains Mono | 13px | 400 |

### Spacing

Base unit: **8px**
- Small: 4px, 8px
- Medium: 12px, 16px, 24px
- Large: 32px, 48px

---

## Common Development Tasks

### Hot Reload

Vite provides instant hot module replacement (HMR). Changes to `.jsx` files update in the browser **without refresh**.

### Linting

```bash
# Run ESLint
npm run lint

# Auto-fix issues
npm run lint -- --fix
```

### Building for Production

```bash
# Create optimized production build
npm run build

# Preview production build locally
npm run preview
```

**Output:** `dist/` directory contains production-ready files.

### Deploying to EKS

Production deployment uses ArgoCD GitOps. Per ADR-049, use Podman for local builds:

```bash
# Build container image (Podman-first per ADR-049)
podman build --platform linux/amd64 \
  -t 123456789012.dkr.ecr.us-east-1.amazonaws.com/aura-frontend:latest \
  -f deploy/docker/frontend/Dockerfile .

# Push to ECR
aws ecr get-login-password --region us-east-1 | \
  podman login --username AWS --password-stdin \
  123456789012.dkr.ecr.us-east-1.amazonaws.com
podman push 123456789012.dkr.ecr.us-east-1.amazonaws.com/aura-frontend:latest

# ArgoCD auto-syncs within 3 minutes
kubectl get pods -n default | grep frontend
```

---

## Troubleshooting

### Issue: Port 5173 Already in Use

**Error:**
```
Port 5173 is in use, trying another one...
```

**Solution:**
```bash
# Kill process on port 5173
lsof -ti:5173 | xargs kill -9

# Or specify a different port
npm run dev -- --port 3000
```

---

### Issue: API Proxy Not Working

**Error:** API calls to `/api/v1/approvals` return 404.

**Solution:**
1. Check backend is running: `curl http://localhost:8000/health`
2. Check `vite.config.js` proxy configuration:
   ```javascript
   server: {
     proxy: {
       '/api': {
         target: 'http://localhost:8000',
         changeOrigin: true,
       }
     }
   }
   ```
3. Restart Vite dev server: `npm run dev`

---

### Issue: Blank White Screen

**Error:** Frontend loads but shows blank page.

**Solution:**
1. Check browser console (F12) for JavaScript errors
2. Check if `dist/` folder exists (if running `npm run preview`)
3. Clear browser cache and hard reload (Ctrl+Shift+R)
4. Delete `node_modules` and reinstall: `rm -rf node_modules && npm install`

---

### Issue: Tailwind Styles Not Applying

**Error:** Components render but have no styling.

**Solution:**
1. Check `tailwind.config.js` content paths include your files
2. Restart Vite dev server
3. Rebuild: `npm run build`

---

## Next Steps

### For Designers
1. Review design system in `agent-config/design-workflows/design-principles.md`
2. Customize colors in `tailwind.config.js`
3. Add new components to `src/components/`

### For Developers
1. Add new API endpoints in backend (`src/api/`)
2. Create new React components in `frontend/src/components/`
3. Add routes in `frontend/src/App.jsx`
4. Test with `npm run lint` and `npm run build`

### For Product Managers
1. View HITL Approval Dashboard at http://localhost:5173/approvals
2. Review approval workflow in `docs/design/HITL_SANDBOX_ARCHITECTURE.md`
3. Test user flows with mock data

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `frontend/package.json` | Dependencies and scripts |
| `frontend/vite.config.js` | Vite configuration and proxy |
| `frontend/tailwind.config.js` | Tailwind CSS configuration |
| `frontend/src/App.jsx` | Main app component and routing |
| `frontend/src/main.jsx` | React entry point |
| `frontend/src/index.css` | Global styles and Tailwind imports |
| `frontend/src/components/ApprovalDashboard.jsx` | HITL approval interface |
| `frontend/README.md` | Quick start guide |

---

## Additional Resources

- **Design System:** `agent-config/design-workflows/design-principles.md`
- **HITL Architecture:** `docs/design/HITL_SANDBOX_ARCHITECTURE.md`
- **API Documentation:** http://localhost:8000/docs (when backend running)
- **React Docs:** https://react.dev/
- **Vite Docs:** https://vitejs.dev/
- **Tailwind CSS:** https://tailwindcss.com/

---

## Quick Commands Reference

```bash
# Install dependencies
npm install

# Start dev server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Run linter
npm run lint

# Start backend (from project root)
uvicorn src.api.main:app --reload
```

---

**Need Help?** Check the browser console (F12) for errors or review logs in the terminal running `npm run dev`.
