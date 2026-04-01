# Project Aura Frontend - Dev Mode Runbook

**Version:** 1.0
**Last Updated:** December 8, 2025
**Audience:** Developers, UI/UX Designers, Product Managers

---

## Overview

Dev Mode is a local development feature that **bypasses AWS Cognito authentication** and MFA requirements, allowing developers to:

- View and test all UI components without logging in
- Access role-protected pages (approvals, red team, integrations)
- Iterate on frontend designs quickly
- Test user flows without external dependencies

**⚠️ IMPORTANT:** Dev Mode is for **local development only**. Never enable it in production.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [How Dev Mode Works](#how-dev-mode-works)
3. [Configuration Options](#configuration-options)
4. [Mock User Customization](#mock-user-customization)
5. [Accessing Protected Routes](#accessing-protected-routes)
6. [Switching Between Dev and Production Auth](#switching-between-dev-and-production-auth)
7. [Troubleshooting](#troubleshooting)
8. [Security Considerations](#security-considerations)

---

## Quick Start

### Enable Dev Mode

**Step 1: Configure Environment**

Edit `frontend/.env.local`:

```bash
# DEV MODE - Bypass authentication for local development
VITE_DEV_MODE=true

# Mock user details (optional - defaults provided)
VITE_MOCK_USER_EMAIL=dev@aenealabs.com
VITE_MOCK_USER_NAME=Developer
VITE_MOCK_USER_ROLE=admin
```

**Step 2: Restart Frontend**

```bash
cd frontend
npm run dev
```

**Step 3: Verify Dev Mode**

Open http://localhost:5173/ in your browser and check the console (F12):

```
🔧 DEV MODE: Auto-login with mock user
```

You should be automatically logged in and see the dashboard.

---

## How Dev Mode Works

### Authentication Flow Comparison

| Step | Production Auth | Dev Mode Auth |
|------|----------------|---------------|
| 1. User visits app | Redirect to Cognito login | Auto-login with mock user |
| 2. Login page | Cognito hosted UI with MFA | Skipped entirely |
| 3. OAuth callback | Exchange code for tokens | Mock tokens generated |
| 4. User session | Real JWT tokens from Cognito | Mock tokens (non-expiring) |
| 5. Role check | Based on Cognito groups | Based on `VITE_MOCK_USER_ROLE` |

### What Gets Mocked

**✅ Mocked in Dev Mode:**
- User authentication state (`isAuthenticated = true`)
- User profile (email, name, role, groups)
- Access tokens (mock JWT format)
- Role-based access control (using mock role)

**❌ NOT Mocked (Still Real):**
- Backend API calls (must have backend running)
- Database queries (Neptune, OpenSearch, DynamoDB)
- AWS services (Bedrock, S3, etc.)

---

## Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_DEV_MODE` | `false` | Enable/disable dev mode |
| `VITE_MOCK_USER_EMAIL` | `dev@aenealabs.com` | Mock user email |
| `VITE_MOCK_USER_NAME` | `Developer` | Mock user display name |
| `VITE_MOCK_USER_ROLE` | `admin` | Mock user role (see roles below) |

### Available Roles

Configure `VITE_MOCK_USER_ROLE` to test different permission levels:

| Role | Access Level | Can Access |
|------|--------------|------------|
| **admin** | Full access | All pages and features |
| **security-engineer** | Security + approvals | Approvals, Red Team, Incidents, Dashboard |
| **developer** | Read-only | Dashboard, Incidents (no approvals) |
| **viewer** | Minimal | Dashboard only |

### Example Configurations

**Admin User (Default):**
```bash
VITE_DEV_MODE=true
VITE_MOCK_USER_EMAIL=admin@aenealabs.com
VITE_MOCK_USER_NAME=Admin User
VITE_MOCK_USER_ROLE=admin
```

**Security Engineer:**
```bash
VITE_DEV_MODE=true
VITE_MOCK_USER_EMAIL=security@aenealabs.com
VITE_MOCK_USER_NAME=Security Engineer
VITE_MOCK_USER_ROLE=security-engineer
```

**Developer (Limited Access):**
```bash
VITE_DEV_MODE=true
VITE_MOCK_USER_EMAIL=dev@aenealabs.com
VITE_MOCK_USER_NAME=Developer
VITE_MOCK_USER_ROLE=developer
```

---

## Mock User Customization

### Testing Different User Personas

Create multiple `.env.local` files for different personas:

**`.env.local.admin`**
```bash
VITE_DEV_MODE=true
VITE_MOCK_USER_EMAIL=admin@aenealabs.com
VITE_MOCK_USER_NAME=Sarah Chen (Admin)
VITE_MOCK_USER_ROLE=admin
```

**`.env.local.security`**
```bash
VITE_DEV_MODE=true
VITE_MOCK_USER_EMAIL=security@aenealabs.com
VITE_MOCK_USER_NAME=Marcus Rodriguez (Security)
VITE_MOCK_USER_ROLE=security-engineer
```

**Switch personas:**
```bash
# Use admin persona
cp .env.local.admin .env.local
npm run dev

# Use security engineer persona
cp .env.local.security .env.local
npm run dev
```

### Mock User Object Structure

The mock user created in dev mode has this structure:

```javascript
{
  id: 'dev-user-123',
  email: 'dev@aenealabs.com',
  emailVerified: true,
  name: 'Developer',
  groups: ['admin', 'security-engineer'],
  role: 'admin'
}
```

### Mock Tokens Structure

```javascript
{
  access_token: 'mock-dev-token-1733699999999',
  id_token: 'mock-dev-token-1733699999999',
  refresh_token: 'mock-dev-token-1733699999999',
  expires_in: 3600,
  token_type: 'Bearer'
}
```

---

## Accessing Protected Routes

With dev mode enabled, you can access all routes regardless of protection level:

### Public Routes (No Auth Required)

| Route | Component | Dev Mode Needed? |
|-------|-----------|------------------|
| `/login` | LoginPage | No (public) |
| `/auth/callback` | AuthCallback | No (public) |

### Protected Routes (Auth Required)

| Route | Component | Required Role | Dev Mode Bypass? |
|-------|-----------|---------------|------------------|
| `/` | Dashboard | Any authenticated | ✅ Yes |
| `/projects` | GraphRAG Explorer | Any authenticated | ✅ Yes |
| `/incidents` | Incident Investigations | Any authenticated | ✅ Yes |
| `/settings` | Settings Page | Any authenticated | ✅ Yes |

### Role-Protected Routes

| Route | Component | Required Role | Dev Mode Bypass? |
|-------|-----------|---------------|------------------|
| `/approvals` | HITL Approvals | admin, security-engineer | ✅ Yes (if role matches) |
| `/security/red-team` | Red Team Dashboard | admin, security-engineer | ✅ Yes (if role matches) |
| `/settings/integrations` | Integration Hub | admin | ✅ Yes (if role matches) |
| `/agents/registry` | Agent Registry | admin, security-engineer | ✅ Yes (if role matches) |

### Testing Role-Based Access

**Scenario:** Test what a security engineer can see

1. Edit `.env.local`:
   ```bash
   VITE_MOCK_USER_ROLE=security-engineer
   ```

2. Restart frontend: `npm run dev`

3. Test access:
   - ✅ Can access `/approvals` (has required role)
   - ✅ Can access `/security/red-team` (has required role)
   - ❌ Cannot access `/settings/integrations` (admin only)

**Expected:** You'll see "Access Denied" on admin-only pages.

---

## Switching Between Dev and Production Auth

### Development → Production

**Step 1: Disable Dev Mode**

Edit `frontend/.env.local`:
```bash
VITE_DEV_MODE=false
```

**Step 2: Configure Cognito for Local Development**

```bash
# Fetch Cognito configuration from SSM Parameter Store (no hardcoded values!)
export AWS_PROFILE=aura-admin
VITE_COGNITO_USER_POOL_ID=$(aws ssm get-parameter --name /aura/dev/cognito/user-pool-id --query Parameter.Value --output text)
VITE_COGNITO_CLIENT_ID=$(aws ssm get-parameter --name /aura/dev/cognito/client-id --query Parameter.Value --output text)
VITE_COGNITO_DOMAIN=$(aws ssm get-parameter --name /aura/dev/cognito/domain --query Parameter.Value --output text)

# Or get all at once:
aws ssm get-parameters-by-path --path /aura/dev/cognito --query 'Parameters[*].[Name,Value]' --output table

# IMPORTANT: Update redirect URLs for localhost
VITE_REDIRECT_SIGN_IN=http://localhost:5173/auth/callback
VITE_REDIRECT_SIGN_OUT=http://localhost:5173/login
```

**Step 3: Update Cognito Callback URLs (One-Time Setup)**

In AWS Console → Cognito → App Client Settings:
- Add `http://localhost:5173/auth/callback` to allowed callback URLs
- Add `http://localhost:5173/login` to allowed sign-out URLs

**Step 4: Restart Frontend**
```bash
npm run dev
```

You'll now see the real Cognito login page with MFA.

### Production → Development

Just set `VITE_DEV_MODE=true` and restart:

```bash
# Quick toggle
echo "VITE_DEV_MODE=true" >> frontend/.env.local
cd frontend && npm run dev
```

---

## Troubleshooting

### Issue: Dev Mode Not Working (Still Redirects to Login)

**Symptoms:**
- Browser redirects to `/login` instead of auto-login
- Console doesn't show "🔧 DEV MODE: Auto-login with mock user"

**Solutions:**

1. **Check environment variable:**
   ```bash
   # Verify VITE_DEV_MODE=true exists
   cat frontend/.env.local | grep DEV_MODE
   ```

2. **Restart frontend completely:**
   ```bash
   # Kill the dev server (Ctrl+C)
   # Clear browser cache (Cmd+Shift+R or Ctrl+Shift+R)
   npm run dev
   ```

3. **Check console for errors:**
   - Open browser console (F12)
   - Look for authentication errors
   - Verify "🔧 DEV MODE" message appears

---

### Issue: Access Denied on Protected Routes

**Symptoms:**
- See "Access Denied" page
- Message: "You don't have permission to access this page"

**Solutions:**

1. **Check mock user role:**
   ```bash
   # View current role
   cat frontend/.env.local | grep MOCK_USER_ROLE
   ```

2. **Update to admin role:**
   ```bash
   # Edit .env.local
   VITE_MOCK_USER_ROLE=admin
   ```

3. **Verify role in browser console:**
   ```javascript
   // Type in browser console:
   console.log(JSON.parse(localStorage.getItem('aura_user')))
   ```

   Expected output:
   ```javascript
   {
     id: "dev-user-123",
     email: "dev@aenealabs.com",
     role: "admin",  // Should match your .env.local
     groups: ["admin", "security-engineer"]
   }
   ```

---

### Issue: API Calls Failing (404, 401 errors)

**Symptoms:**
- UI loads but data doesn't appear
- Console shows API errors
- Backend returns 401 Unauthorized

**Solutions:**

1. **Verify backend is running:**
   ```bash
   curl http://localhost:5713/health
   # Should return: {"status":"healthy"}
   ```

2. **Check API URL configuration:**
   ```bash
   cat frontend/.env.local | grep API_URL
   # Should be: VITE_API_URL=http://localhost:5713/api/v1
   ```

3. **Backend may require real AWS credentials:**
   - Dev mode only mocks **frontend auth**
   - Backend still needs AWS credentials for DynamoDB, Neptune, etc.
   - Ensure `.env.local` (root) has `AWS_REGION=us-east-1`

---

### Issue: Mock User Not Appearing in UI

**Symptoms:**
- Top-right user menu shows blank or "undefined"
- User profile missing

**Solutions:**

1. **Clear localStorage:**
   ```javascript
   // In browser console:
   localStorage.clear();
   location.reload();
   ```

2. **Verify mock user creation:**
   ```javascript
   // In browser console:
   console.log(localStorage.getItem('aura_user'));
   ```

   Should show:
   ```json
   {"id":"dev-user-123","email":"dev@aenealabs.com","name":"Developer","role":"admin"}
   ```

---

### Issue: Changes to .env.local Not Taking Effect

**Symptoms:**
- Updated `VITE_MOCK_USER_ROLE` but still using old role
- Changed `VITE_DEV_MODE` but behavior unchanged

**Solutions:**

1. **Vite requires full restart for .env changes:**
   ```bash
   # Stop dev server (Ctrl+C)
   # Restart (don't just save the file)
   npm run dev
   ```

2. **Clear browser cache:**
   - Hard refresh: `Cmd+Shift+R` (Mac) or `Ctrl+Shift+R` (Windows)
   - Or clear cache manually in browser settings

3. **Verify environment variables loaded:**
   ```javascript
   // In browser console:
   console.log(import.meta.env.VITE_DEV_MODE);
   console.log(import.meta.env.VITE_MOCK_USER_ROLE);
   ```

---

## Security Considerations

### ⚠️ Critical Security Rules

1. **Never deploy with dev mode enabled**
   - Set `VITE_DEV_MODE=false` in production `.env`
   - CI/CD should fail if `VITE_DEV_MODE=true` detected in production build

2. **Never commit `.env.local` to git**
   - Already in `.gitignore`
   - Contains local development settings only

3. **Dev mode bypasses all authentication**
   - Any user can access any page
   - No actual validation of credentials
   - Only use on localhost

4. **Backend still requires real AWS credentials**
   - Dev mode doesn't mock AWS SDK calls
   - Protect your AWS credentials (`~/.aws/credentials`)

### Safe Usage Checklist

✅ **Safe:**
- Using dev mode on `localhost:5173`
- Testing UI designs without backend
- Iterating on components quickly
- Demonstrating UI to stakeholders (local only)

❌ **Unsafe:**
- Enabling dev mode in production
- Deploying with `VITE_DEV_MODE=true`
- Using dev mode on publicly accessible servers
- Sharing `.env.local` files with credentials

### Production Build Verification

Before deploying, verify dev mode is disabled:

```bash
# Check production build
npm run build

# Verify .env.production
cat .env.production | grep DEV_MODE
# Should NOT have VITE_DEV_MODE=true

# Or use explicit production env
VITE_DEV_MODE=false npm run build
```

---

## Common Development Workflows

### Workflow 1: UI Design Iteration

**Goal:** Quickly iterate on UI components without authentication

```bash
# 1. Enable dev mode
echo "VITE_DEV_MODE=true" > frontend/.env.local

# 2. Start frontend only (no backend needed for static UI)
cd frontend
npm run dev

# 3. Access any page directly
open http://localhost:5173/approvals
open http://localhost:5173/security/red-team

# 4. Edit components in src/components/
# 5. See changes instantly (hot reload)
```

---

### Workflow 2: Full-Stack Development

**Goal:** Develop features with real backend API

```bash
# Terminal 1: Backend
export AWS_REGION=us-east-1
uvicorn src.api.main:app --reload --port 5713

# Terminal 2: Frontend (dev mode)
cd frontend
echo "VITE_DEV_MODE=true" > .env.local
echo "VITE_API_URL=http://localhost:5713/api/v1" >> .env.local
npm run dev

# Access UI with auto-login + real backend data
open http://localhost:5173/
```

---

### Workflow 3: Role-Based Access Testing

**Goal:** Test UI behavior for different user roles

```bash
# Test admin access
echo "VITE_MOCK_USER_ROLE=admin" >> frontend/.env.local
npm run dev
# Verify: Can access all pages

# Test security engineer
echo "VITE_MOCK_USER_ROLE=security-engineer" >> frontend/.env.local
npm run dev
# Verify: Can access approvals, red team (not integrations)

# Test viewer
echo "VITE_MOCK_USER_ROLE=viewer" >> frontend/.env.local
npm run dev
# Verify: Can only access dashboard
```

---

## Quick Reference Commands

```bash
# Enable dev mode
echo "VITE_DEV_MODE=true" >> frontend/.env.local && cd frontend && npm run dev

# Disable dev mode
echo "VITE_DEV_MODE=false" >> frontend/.env.local && cd frontend && npm run dev

# Set admin role
echo "VITE_MOCK_USER_ROLE=admin" >> frontend/.env.local

# Set security engineer role
echo "VITE_MOCK_USER_ROLE=security-engineer" >> frontend/.env.local

# Clear frontend cache
rm -rf frontend/.vite && cd frontend && npm run dev

# View current dev mode status
cat frontend/.env.local | grep DEV_MODE

# Check if auto-logged in
# (In browser console): localStorage.getItem('aura_user')
```

---

## Additional Resources

- **Frontend Runbook:** `docs/FRONTEND_UI_RUNBOOK.md`
- **Authentication Documentation:** `frontend/src/context/AuthContext.jsx`
- **Protected Routes:** `frontend/src/components/ProtectedRoute.jsx`
- **Cognito Configuration:** `frontend/src/config/auth.js`

---

## FAQ

**Q: Can I use dev mode with the production backend?**
A: Not recommended. The production backend expects real Cognito tokens. Dev mode only mocks frontend auth.

**Q: Does dev mode work with the deployed app?**
A: No. Dev mode only works on localhost. Production builds should have `VITE_DEV_MODE=false`.

**Q: Can I customize the mock user groups?**
A: Yes, edit `frontend/src/context/AuthContext.jsx` in the `createMockUser()` function.

**Q: Why am I still seeing the login page with dev mode enabled?**
A: Restart the dev server completely (`Ctrl+C`, then `npm run dev`). Vite needs a full restart for .env changes.

**Q: Can I test MFA flow in dev mode?**
A: No. Dev mode bypasses all authentication. To test MFA, disable dev mode and use real Cognito.

---

**Last Updated:** December 8, 2025
**Maintained By:** Aenea Labs Engineering Team
