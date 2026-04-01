import { useState, useEffect, memo } from 'react';
import {
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  ShieldCheckIcon,
  CodeBracketIcon,
  ChevronRightIcon,
  FunnelIcon,
  MagnifyingGlassIcon,
  ArrowPathIcon,
  DocumentTextIcon,
  ChatBubbleLeftRightIcon,
  BeakerIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';
import { PageSkeleton } from './ui/LoadingSkeleton';
import { useToast } from './ui/Toast';
import { listApprovals, approveApproval, rejectApproval, requestChanges } from '../services/approvalApi';

// Default mock approvals data - used when API is unavailable
// Following the same pattern as useDashboardData.js for graceful degradation
const DEFAULT_APPROVALS = [
  {
    id: 'apr-001',
    title: 'SQL Injection Fix in Authentication Handler',
    status: 'pending',
    vulnerability: {
      severity: 'critical',
      description: 'User input in login query is not properly sanitized, allowing SQL injection attacks that could bypass authentication or extract sensitive data.',
      cve: 'CVE-2024-1234',
      cwe: 'CWE-89',
    },
    patch: {
      file: 'src/auth/handlers/login.py',
      linesChanged: 24,
      generatedBy: 'Coder Agent',
      sandboxStatus: 'passed',
      testResults: { passed: 47, failed: 0, skipped: 2 },
      diff: `diff --git a/src/auth/handlers/login.py b/src/auth/handlers/login.py
index 1a2b3c4..5d6e7f8 100644
--- a/src/auth/handlers/login.py
+++ b/src/auth/handlers/login.py
@@ -15,8 +15,12 @@ from app.db import get_db_connection
 async def authenticate_user(username: str, password: str):
     """Authenticate user with username and password."""
     conn = get_db_connection()
-    # VULNERABLE: Direct string interpolation
-    query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
+    # FIXED: Use parameterized queries to prevent SQL injection
+    query = "SELECT * FROM users WHERE username = %s AND password_hash = %s"
+    password_hash = hash_password(password)
     cursor = conn.cursor()
-    cursor.execute(query)
+    cursor.execute(query, (username, password_hash))
     return cursor.fetchone()`,
    },
    affectedFiles: ['src/auth/handlers/login.py', 'src/auth/utils/validators.py'],
    createdAt: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    requestedBy: 'Coder Agent',
  },
  {
    id: 'apr-002',
    title: 'XSS Prevention in User Profile Display',
    status: 'pending',
    vulnerability: {
      severity: 'high',
      description: 'User-supplied profile data is rendered without proper HTML encoding, enabling cross-site scripting attacks.',
      cve: 'CVE-2024-2345',
      cwe: 'CWE-79',
    },
    patch: {
      file: 'src/web/views/profile.jsx',
      linesChanged: 18,
      generatedBy: 'Coder Agent',
      sandboxStatus: 'passed',
      testResults: { passed: 32, failed: 0, skipped: 1 },
      diff: `diff --git a/src/web/views/profile.jsx b/src/web/views/profile.jsx
index 2b3c4d5..6e7f8g9 100644
--- a/src/web/views/profile.jsx
+++ b/src/web/views/profile.jsx
@@ -22,7 +22,9 @@ function UserProfile({ user }) {
   return (
     <div className="profile-container">
       <h1>{user.displayName}</h1>
-      <div dangerouslySetInnerHTML={{ __html: user.bio }} />
+      <div className="user-bio">
+        {DOMPurify.sanitize(user.bio, { ALLOWED_TAGS: ['b', 'i', 'em', 'strong'] })}
+      </div>
     </div>
   );
 }`,
    },
    affectedFiles: ['src/web/views/profile.jsx'],
    createdAt: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString(),
    requestedBy: 'Coder Agent',
  },
  {
    id: 'apr-003',
    title: 'Hardcoded API Key Removal',
    status: 'sandbox_testing',
    vulnerability: {
      severity: 'critical',
      description: 'AWS credentials are hardcoded in the configuration file, risking unauthorized cloud resource access if the repository is exposed.',
      cve: null,
      cwe: 'CWE-798',
    },
    patch: {
      file: 'src/config/aws_config.py',
      linesChanged: 31,
      generatedBy: 'Coder Agent',
      sandboxStatus: 'testing',
      testResults: null,
      diff: `diff --git a/src/config/aws_config.py b/src/config/aws_config.py
index 3c4d5e6..7f8g9h0 100644
--- a/src/config/aws_config.py
+++ b/src/config/aws_config.py
@@ -1,12 +1,18 @@
-# VULNERABLE: Hardcoded credentials
-AWS_ACCESS_KEY = "<REDACTED_ACCESS_KEY>"
-AWS_SECRET_KEY = "<REDACTED_SECRET_KEY>"
-AWS_REGION = "us-east-1"
+import os
+from functools import lru_cache
+
+@lru_cache()
+def get_aws_config():
+    """Load AWS configuration from environment or SSM."""
+    return {
+        'access_key': os.environ.get('AWS_ACCESS_KEY_ID'),
+        'secret_key': os.environ.get('AWS_SECRET_ACCESS_KEY'),
+        'region': os.environ.get('AWS_REGION', 'us-east-1'),
+    }`,
    },
    affectedFiles: ['src/config/aws_config.py', 'src/services/s3_client.py', 'src/services/dynamodb_client.py'],
    createdAt: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString(),
    requestedBy: 'Security Scanner',
  },
  {
    id: 'apr-004',
    title: 'Path Traversal Fix in File Upload',
    status: 'pending',
    vulnerability: {
      severity: 'high',
      description: 'File upload endpoint allows path traversal sequences, enabling attackers to write files outside the intended directory.',
      cve: 'CVE-2024-3456',
      cwe: 'CWE-22',
    },
    patch: {
      file: 'src/api/upload.py',
      linesChanged: 15,
      generatedBy: 'Coder Agent',
      sandboxStatus: 'passed',
      testResults: { passed: 28, failed: 0, skipped: 0 },
      diff: `diff --git a/src/api/upload.py b/src/api/upload.py
index 4d5e6f7..8g9h0i1 100644
--- a/src/api/upload.py
+++ b/src/api/upload.py
@@ -8,7 +8,12 @@ UPLOAD_DIR = Path("/app/uploads")
 @router.post("/upload")
 async def upload_file(file: UploadFile):
-    file_path = UPLOAD_DIR / file.filename
+    # Sanitize filename to prevent path traversal
+    safe_filename = Path(file.filename).name
+    if not safe_filename or safe_filename.startswith('.'):
+        raise HTTPException(400, "Invalid filename")
+    file_path = UPLOAD_DIR / safe_filename
+    file_path = file_path.resolve()
+    if not str(file_path).startswith(str(UPLOAD_DIR.resolve())):
+        raise HTTPException(400, "Invalid file path")
     async with aiofiles.open(file_path, 'wb') as f:
         await f.write(await file.read())`,
    },
    affectedFiles: ['src/api/upload.py'],
    createdAt: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString(),
    requestedBy: 'Coder Agent',
  },
  {
    id: 'apr-005',
    title: 'Insecure Deserialization Mitigation',
    status: 'approved',
    vulnerability: {
      severity: 'critical',
      description: 'Pickle deserialization of untrusted data allows remote code execution through crafted payloads.',
      cve: 'CVE-2024-4567',
      cwe: 'CWE-502',
    },
    patch: {
      file: 'src/services/cache_service.py',
      linesChanged: 22,
      generatedBy: 'Coder Agent',
      sandboxStatus: 'passed',
      testResults: { passed: 51, failed: 0, skipped: 3 },
      diff: `diff --git a/src/services/cache_service.py b/src/services/cache_service.py
index 5e6f7g8..9h0i1j2 100644
--- a/src/services/cache_service.py
+++ b/src/services/cache_service.py
@@ -1,10 +1,12 @@
-import pickle
+import json
+from typing import Any

 class CacheService:
-    def deserialize(self, data: bytes):
-        # VULNERABLE: Unsafe deserialization
-        return pickle.loads(data)
+    def deserialize(self, data: bytes) -> Any:
+        # FIXED: Use JSON for safe deserialization
+        return json.loads(data.decode('utf-8'))
+
+    def serialize(self, obj: Any) -> bytes:
+        return json.dumps(obj).encode('utf-8')`,
    },
    affectedFiles: ['src/services/cache_service.py', 'src/api/session.py'],
    createdAt: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
    requestedBy: 'Coder Agent',
    approvedBy: 'security@aenealabs.com',
    approvedAt: new Date(Date.now() - 20 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: 'apr-006',
    title: 'CSRF Token Validation',
    status: 'rejected',
    vulnerability: {
      severity: 'medium',
      description: 'State-changing endpoints lack CSRF token validation, allowing cross-site request forgery attacks.',
      cve: null,
      cwe: 'CWE-352',
    },
    patch: {
      file: 'src/middleware/csrf.py',
      linesChanged: 45,
      generatedBy: 'Coder Agent',
      sandboxStatus: 'failed',
      testResults: { passed: 18, failed: 4, skipped: 1 },
      diff: `diff --git a/src/middleware/csrf.py b/src/middleware/csrf.py
index 6f7g8h9..0i1j2k3 100644
--- a/src/middleware/csrf.py
+++ b/src/middleware/csrf.py
@@ -1,5 +1,20 @@
+import secrets
+from fastapi import Request, HTTPException
+
+def generate_csrf_token():
+    return secrets.token_urlsafe(32)
+
+async def validate_csrf(request: Request):
+    if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
+        token = request.headers.get('X-CSRF-Token')
+        session_token = request.session.get('csrf_token')
+        if not token or token != session_token:
+            raise HTTPException(403, "Invalid CSRF token")`,
    },
    affectedFiles: ['src/middleware/csrf.py', 'src/api/main.py'],
    createdAt: new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString(),
    requestedBy: 'Coder Agent',
    rejectedBy: 'security@aenealabs.com',
    rejectionReason: 'Implementation breaks existing API integrations. Needs coordination with frontend team.',
  },
  {
    id: 'apr-007',
    title: 'Rate Limiting for Authentication Endpoints',
    status: 'sandbox_testing',
    vulnerability: {
      severity: 'medium',
      description: 'Authentication endpoints lack rate limiting, enabling brute force attacks against user credentials.',
      cve: null,
      cwe: 'CWE-307',
    },
    patch: {
      file: 'src/api/auth_routes.py',
      linesChanged: 28,
      generatedBy: 'Coder Agent',
      sandboxStatus: 'testing',
      testResults: null,
      diff: `diff --git a/src/api/auth_routes.py b/src/api/auth_routes.py
index 7g8h9i0..1j2k3l4 100644
--- a/src/api/auth_routes.py
+++ b/src/api/auth_routes.py
@@ -1,8 +1,15 @@
 from fastapi import APIRouter, Depends
+from slowapi import Limiter
+from slowapi.util import get_remote_address
+
+limiter = Limiter(key_func=get_remote_address)
 router = APIRouter()

 @router.post("/login")
+@limiter.limit("5/minute")
 async def login(credentials: LoginRequest):
     # Authenticate user
     pass`,
    },
    affectedFiles: ['src/api/auth_routes.py', 'src/config/rate_limits.py'],
    createdAt: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
    requestedBy: 'Security Scanner',
  },
];

// Severity styles following design system
const SEVERITY_STYLES = {
  critical: {
    badge: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
    border: 'border-critical-500',
    selectedBorder: 'border-critical-500 dark:border-critical-400',
    bg: 'bg-critical-50 dark:bg-critical-900/20',
    text: 'text-critical-600 dark:text-critical-400',
  },
  high: {
    badge: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    border: 'border-warning-500',
    selectedBorder: 'border-warning-500 dark:border-warning-400',
    bg: 'bg-warning-50 dark:bg-warning-900/20',
    text: 'text-warning-600 dark:text-warning-400',
  },
  medium: {
    badge: 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400',
    border: 'border-olive-500',
    selectedBorder: 'border-olive-500 dark:border-olive-400',
    bg: 'bg-olive-50 dark:bg-olive-900/20',
    text: 'text-olive-600 dark:text-olive-400',
  },
  low: {
    badge: 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400',
    border: 'border-aura-500',
    selectedBorder: 'border-aura-500 dark:border-aura-400',
    bg: 'bg-aura-50 dark:bg-aura-900/20',
    text: 'text-aura-600 dark:text-aura-400',
  },
};

const STATUS_STYLES = {
  pending: {
    badge: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    icon: ClockIcon,
    label: 'Pending Review',
  },
  approved: {
    badge: 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400',
    icon: CheckCircleIcon,
    label: 'Approved',
  },
  rejected: {
    badge: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
    icon: XCircleIcon,
    label: 'Rejected',
  },
  sandbox_testing: {
    badge: 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400',
    icon: BeakerIcon,
    label: 'Testing',
  },
};


// Format relative time
function formatRelativeTime(date) {
  const now = new Date();
  const then = new Date(date);
  const seconds = Math.floor((now - then) / 1000);

  if (seconds < 60) return 'Just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return then.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

// Diff Viewer Component
function DiffViewer({ diff }) {
  const [collapsed, setCollapsed] = useState({});

  if (!diff) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-surface-400 dark:text-surface-500">
        <CodeBracketIcon className="w-12 h-12 mb-3" />
        <p className="text-sm">Diff not available yet</p>
        <p className="text-xs mt-1">Sandbox testing in progress...</p>
      </div>
    );
  }

  const lines = diff.split('\n');
  const hunks = [];
  let currentHunk = null;

  lines.forEach((line, index) => {
    if (line.startsWith('@@')) {
      if (currentHunk) hunks.push(currentHunk);
      currentHunk = { header: line, lines: [], startIndex: index };
    } else if (currentHunk) {
      currentHunk.lines.push({ content: line, index });
    } else if (line.startsWith('diff ') || line.startsWith('index ') || line.startsWith('---') || line.startsWith('+++')) {
      // File headers
      if (!currentHunk) {
        hunks.push({ header: line, lines: [], isFileHeader: true, startIndex: index });
      }
    }
  });
  if (currentHunk) hunks.push(currentHunk);

  // IDE-like diff colors (VS Code style)
  const getLineClass = (line) => {
    if (line.startsWith('+') && !line.startsWith('+++')) {
      // Added lines: green background with high contrast
      return 'bg-green-100 dark:bg-[#1a3d1a] text-green-900 dark:text-green-200';
    }
    if (line.startsWith('-') && !line.startsWith('---')) {
      // Removed lines: critical red (matches CRITICAL status badge)
      return 'bg-critical-100 dark:bg-critical-900/50 text-critical-800 dark:text-critical-400';
    }
    return 'text-surface-700 dark:text-surface-300 bg-surface-50 dark:bg-surface-900';
  };

  const getLinePrefix = (line) => {
    if (line.startsWith('+') && !line.startsWith('+++')) {
      return 'bg-green-200 dark:bg-[#234d23] text-green-800 dark:text-green-300 font-medium';
    }
    if (line.startsWith('-') && !line.startsWith('---')) {
      return 'bg-critical-200 dark:bg-critical-800/60 text-critical-700 dark:text-critical-300 font-medium';
    }
    return 'bg-surface-100 dark:bg-surface-800 text-surface-500 dark:text-surface-400';
  };

  return (
    <div className="font-mono text-sm rounded-lg overflow-hidden border border-surface-200 dark:border-surface-700">
      {hunks.map((hunk, hunkIndex) => {
        const isCollapsed = collapsed[hunkIndex];

        if (hunk.isFileHeader) {
          return (
            <div key={hunkIndex} className="px-4 py-2 bg-surface-100 dark:bg-surface-800 text-surface-500 dark:text-surface-400 text-xs border-b border-surface-200 dark:border-surface-700">
              {hunk.header}
            </div>
          );
        }

        return (
          <div key={hunkIndex} className="border-b border-surface-200 dark:border-surface-700 last:border-b-0">
            {/* Hunk Header */}
            <button
              onClick={() => setCollapsed({ ...collapsed, [hunkIndex]: !isCollapsed })}
              className="w-full px-4 py-2 bg-aura-50 dark:bg-aura-900/20 text-aura-600 dark:text-aura-400 text-left flex items-center justify-between hover:bg-aura-100 dark:hover:bg-aura-900/30 transition-colors"
            >
              <span className="text-xs">{hunk.header}</span>
              {isCollapsed ? <ChevronDownIcon className="w-4 h-4" /> : <ChevronUpIcon className="w-4 h-4" />}
            </button>

            {/* Hunk Lines */}
            {!isCollapsed && (
              <div className="overflow-x-auto">
                {hunk.lines.map((lineObj, lineIndex) => (
                  <div key={lineIndex} className={`flex ${getLineClass(lineObj.content)}`}>
                    <span className={`w-12 flex-shrink-0 text-center py-0.5 text-xs select-none ${getLinePrefix(lineObj.content)}`}>
                      {lineObj.index + 1}
                    </span>
                    <pre className="flex-1 px-4 py-0.5 whitespace-pre-wrap break-all">
                      {lineObj.content}
                    </pre>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// Approval Card Component
// Memoized to prevent re-renders when parent state changes but card props are stable
const ApprovalCard = memo(function ApprovalCard({ approval, isSelected, onClick }) {
  const severity = SEVERITY_STYLES[approval.vulnerability?.severity] || SEVERITY_STYLES.medium;
  const status = STATUS_STYLES[approval.status] || STATUS_STYLES.pending;
  const StatusIcon = status.icon;

  return (
    <button
      onClick={onClick}
      className={`
        w-full text-left p-4 rounded-xl transition-all duration-200
        ${isSelected
          ? `border-2 ${severity.selectedBorder} bg-white dark:bg-surface-800 shadow-lg`
          : 'border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 hover:border-surface-300 dark:hover:border-surface-600 hover:shadow-md'
        }
      `}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`px-2 py-0.5 rounded-full text-xs font-semibold uppercase ${severity.badge}`}>
            {approval.vulnerability?.severity || 'medium'}
          </span>
          <span className={`px-2 py-0.5 rounded-full text-xs font-medium flex items-center gap-1 ${status.badge}`}>
            <StatusIcon className="w-3 h-3" />
            {status.label}
          </span>
        </div>
        <ChevronRightIcon className={`w-5 h-5 flex-shrink-0 transition-transform ${isSelected ? 'rotate-90' : ''} text-surface-400`} />
      </div>

      {/* Title */}
      <h3 className="font-semibold text-surface-900 dark:text-surface-100 mb-2 line-clamp-2">
        {approval.title}
      </h3>

      {/* Description */}
      <p className="text-sm text-surface-600 dark:text-surface-400 line-clamp-2 mb-3">
        {approval.vulnerability?.description || 'No description available'}
      </p>

      {/* Metadata */}
      <div className="flex items-center gap-3 text-xs text-surface-500 dark:text-surface-400 flex-wrap">
        {approval.vulnerability?.cve && (
          <span className="flex items-center gap-1">
            <ShieldCheckIcon className="w-3.5 h-3.5" />
            {approval.vulnerability.cve}
          </span>
        )}
        <span className="flex items-center gap-1">
          <CodeBracketIcon className="w-3.5 h-3.5" />
          {approval.patch.file.split('/').pop()}
        </span>
        <span className="flex items-center gap-1">
          <ClockIcon className="w-3.5 h-3.5" />
          {formatRelativeTime(approval.createdAt)}
        </span>
      </div>
    </button>
  );
});

// Detail Panel Component
function ApprovalDetailPanel({ approval, onApprove, onReject, onRequestChanges, isLoading }) {
  const [comment, setComment] = useState('');
  const [activeTab, setActiveTab] = useState('diff');

  if (!approval) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-surface-400 dark:text-surface-500 p-8">
        <DocumentTextIcon className="w-16 h-16 mb-4" />
        <h3 className="text-lg font-medium mb-2">Select an Approval</h3>
        <p className="text-sm text-center">Choose an approval request from the list to view details and take action</p>
      </div>
    );
  }

  const severity = SEVERITY_STYLES[approval.vulnerability?.severity] || SEVERITY_STYLES.medium;
  const _status = STATUS_STYLES[approval.status] || STATUS_STYLES.pending;

  return (
    <div className="flex-1 flex flex-col bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 overflow-hidden">
      {/* Header */}
      <div className="p-6 border-b border-surface-200 dark:border-surface-700 bg-surface-50/50 dark:bg-surface-800/50">
        <div className="flex items-center gap-2 mb-3">
          <span className={`px-2.5 py-1 rounded-full text-xs font-semibold uppercase ${severity.badge}`}>
            {approval.vulnerability?.severity || 'medium'}
          </span>
          {approval.vulnerability?.cve && (
            <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-surface-100 dark:bg-surface-700 text-surface-700 dark:text-surface-300">
              {approval.vulnerability.cve}
            </span>
          )}
          {approval.vulnerability?.cwe && (
            <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-surface-100 dark:bg-surface-700 text-surface-700 dark:text-surface-300">
              {approval.vulnerability.cwe}
            </span>
          )}
        </div>
        <h2 className="text-xl font-bold text-surface-900 dark:text-surface-100 mb-2">
          {approval.title}
        </h2>
        <p className="text-surface-600 dark:text-surface-400">
          {approval.vulnerability?.description || 'No description available'}
        </p>
      </div>

      {/* Tabs */}
      <div className="border-b border-surface-200 dark:border-surface-700">
        <nav className="flex gap-1 px-4">
          {[
            { id: 'diff', label: 'Code Changes', icon: CodeBracketIcon },
            { id: 'info', label: 'Details', icon: InformationCircleIcon },
            { id: 'tests', label: 'Test Results', icon: BeakerIcon },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`
                flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors
                ${activeTab === tab.id
                  ? 'border-aura-500 text-aura-600 dark:text-aura-400'
                  : 'border-transparent text-surface-500 hover:text-surface-700 dark:hover:text-surface-300'
                }
              `}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {activeTab === 'diff' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-surface-900 dark:text-surface-100">
                Code Changes
              </h3>
              <span className="text-sm text-surface-500 dark:text-surface-400">
                {approval.patch.linesChanged} lines changed
              </span>
            </div>
            <DiffViewer diff={approval.patch.diff} />
          </div>
        )}

        {activeTab === 'info' && (
          <div className="space-y-6">
            {/* Patch Information */}
            <div>
              <h3 className="font-semibold text-surface-900 dark:text-surface-100 mb-3">Patch Details</h3>
              <div className="bg-surface-50 dark:bg-surface-700/50 rounded-lg p-4 space-y-3">
                <div className="flex justify-between">
                  <span className="text-surface-600 dark:text-surface-400">File</span>
                  <span className="font-mono text-sm text-surface-900 dark:text-surface-100">{approval.patch.file}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-surface-600 dark:text-surface-400">Lines Changed</span>
                  <span className="font-semibold text-surface-900 dark:text-surface-100">{approval.patch.linesChanged}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-surface-600 dark:text-surface-400">Generated By</span>
                  <span className="text-surface-900 dark:text-surface-100">{approval.patch.generatedBy}</span>
                </div>
              </div>
            </div>

            {/* Affected Files */}
            {approval.affectedFiles && (
              <div>
                <h3 className="font-semibold text-surface-900 dark:text-surface-100 mb-3">Affected Files</h3>
                <div className="space-y-2">
                  {approval.affectedFiles.map((file, index) => (
                    <div key={index} className="flex items-center gap-2 p-2 bg-surface-50 dark:bg-surface-700/50 rounded-lg">
                      <CodeBracketIcon className="w-4 h-4 text-surface-500" />
                      <span className="font-mono text-sm text-surface-700 dark:text-surface-300">{file}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Request Metadata */}
            <div>
              <h3 className="font-semibold text-surface-900 dark:text-surface-100 mb-3">Request Information</h3>
              <div className="bg-surface-50 dark:bg-surface-700/50 rounded-lg p-4 space-y-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-surface-600 dark:text-surface-400">Request ID</span>
                  <span className="font-mono text-surface-900 dark:text-surface-100">{approval.id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-surface-600 dark:text-surface-400">Requested By</span>
                  <span className="text-surface-900 dark:text-surface-100">{approval.requestedBy}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-surface-600 dark:text-surface-400">Created</span>
                  <span className="text-surface-900 dark:text-surface-100">{new Date(approval.createdAt).toLocaleString()}</span>
                </div>
                {approval.approvedBy && (
                  <>
                    <div className="flex justify-between">
                      <span className="text-surface-600 dark:text-surface-400">Approved By</span>
                      <span className="text-surface-900 dark:text-surface-100">{approval.approvedBy}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-surface-600 dark:text-surface-400">Approved At</span>
                      <span className="text-surface-900 dark:text-surface-100">{new Date(approval.approvedAt).toLocaleString()}</span>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'tests' && (
          <div className="space-y-6">
            {/* Sandbox Status */}
            <div>
              <h3 className="font-semibold text-surface-900 dark:text-surface-100 mb-3">Sandbox Testing</h3>
              <div className="bg-surface-50 dark:bg-surface-700/50 rounded-lg p-4">
                <div className="flex items-center gap-3 mb-4">
                  {approval.patch.sandboxStatus === 'passed' && (
                    <>
                      <CheckCircleIcon className="w-6 h-6 text-olive-500" />
                      <span className="font-medium text-olive-700 dark:text-olive-400">All Tests Passed</span>
                    </>
                  )}
                  {approval.patch.sandboxStatus === 'testing' && (
                    <>
                      <ArrowPathIcon className="w-6 h-6 text-aura-500 animate-spin" />
                      <span className="font-medium text-aura-700 dark:text-aura-400">Testing in Progress...</span>
                    </>
                  )}
                  {approval.patch.sandboxStatus === 'failed' && (
                    <>
                      <XCircleIcon className="w-6 h-6 text-critical-500" />
                      <span className="font-medium text-critical-700 dark:text-critical-400">Tests Failed</span>
                    </>
                  )}
                </div>

                {approval.patch.testResults && (
                  <div className="grid grid-cols-3 gap-4 min-w-0">
                    <div className="text-center p-3 bg-olive-100 dark:bg-olive-900/30 rounded-lg">
                      <p className="text-2xl font-bold text-olive-700 dark:text-olive-400">
                        {approval.patch.testResults.passed}
                      </p>
                      <p className="text-xs text-olive-600 dark:text-olive-500">Passed</p>
                    </div>
                    <div className="text-center p-3 bg-critical-100 dark:bg-critical-900/30 rounded-lg">
                      <p className="text-2xl font-bold text-critical-700 dark:text-critical-400">
                        {approval.patch.testResults.failed}
                      </p>
                      <p className="text-xs text-critical-600 dark:text-critical-500">Failed</p>
                    </div>
                    <div className="text-center p-3 bg-surface-100 dark:bg-surface-600 rounded-lg">
                      <p className="text-2xl font-bold text-surface-700 dark:text-surface-300">
                        {approval.patch.testResults.skipped}
                      </p>
                      <p className="text-xs text-surface-600 dark:text-surface-400">Skipped</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Action Footer */}
      {approval.status === 'pending' && (
        <div className="p-4 border-t border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50">
          {/* Comment Input */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
              Comment (required for reject/changes)
            </label>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Add a comment..."
              rows={2}
              className="w-full px-4 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-aura-500 focus:border-transparent resize-none"
            />
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3">
            <button
              onClick={() => onReject(approval.id, comment)}
              disabled={!comment.trim() || isLoading}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-3 border border-critical-300 dark:border-critical-700 text-critical-600 dark:text-critical-400 rounded-lg font-medium hover:bg-critical-50 dark:hover:bg-critical-900/20 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <XCircleIcon className="w-5 h-5" />
              Reject
            </button>
            <button
              onClick={() => onRequestChanges(approval.id, comment)}
              disabled={!comment.trim() || isLoading}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-warning-500 hover:bg-warning-600 text-white rounded-lg font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <ChatBubbleLeftRightIcon className="w-5 h-5" />
              Request Changes
            </button>
            <button
              onClick={() => onApprove(approval.id)}
              disabled={isLoading}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-olive-500 hover:bg-olive-600 text-white rounded-lg font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <CheckCircleIcon className="w-5 h-5" />
              Approve & Deploy
            </button>
          </div>
          <p className="text-xs text-surface-500 dark:text-surface-400 text-center mt-3">
            Approving will trigger deployment to the target environment
          </p>
        </div>
      )}
    </div>
  );
}

// Main Component
export default function ApprovalDashboard() {
  const [approvals, setApprovals] = useState([]);
  const [selectedApproval, setSelectedApproval] = useState(null);
  const [filter, setFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);

  const { toast } = useToast();

  // Fetch approvals - falls back to mock data when API unavailable
  const fetchApprovals = async () => {
    try {
      const data = await listApprovals();
      setApprovals(data || []);
      setError(null);
    } catch (err) {
      // Graceful degradation: use mock data when API is unavailable
      // This follows the same pattern as useDashboardData.js
      console.warn('Using default approvals data (API unavailable)');
      setApprovals(DEFAULT_APPROVALS);
      setError(null); // Don't show error banner when using mock data
    } finally {
      setLoading(false);
    }
  };

  // Fetch approvals on mount only
  useEffect(() => {
    fetchApprovals();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Handle refresh - falls back to mock data when API unavailable
  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      const data = await listApprovals();
      setApprovals(data || []);
      toast.success('Approvals refreshed');
    } catch (err) {
      // Graceful degradation: use mock data when API is unavailable
      console.warn('Using default approvals data on refresh (API unavailable)');
      setApprovals(DEFAULT_APPROVALS);
      toast.info('Showing demo data (API unavailable)');
    } finally {
      setIsRefreshing(false);
    }
  };

  // Filter approvals
  const filteredApprovals = approvals.filter((approval) => {
    const matchesFilter = filter === 'all' || approval.status === filter;
    const matchesSearch =
      searchQuery === '' ||
      approval.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      approval.vulnerability?.cve?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      approval.patch.file.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesFilter && matchesSearch;
  });

  // Count by status
  const statusCounts = {
    all: approvals.length,
    pending: approvals.filter((a) => a.status === 'pending').length,
    sandbox_testing: approvals.filter((a) => a.status === 'sandbox_testing').length,
    approved: approvals.filter((a) => a.status === 'approved').length,
    rejected: approvals.filter((a) => a.status === 'rejected').length,
  };

  const handleApprove = async (id) => {
    setActionLoading(true);
    try {
      await approveApproval(id);
      setApprovals((prev) =>
        prev.map((a) =>
          a.id === id ? { ...a, status: 'approved', approvedBy: 'reviewer@aenealabs.com', approvedAt: new Date().toISOString() } : a
        )
      );
      setSelectedApproval(null);
      toast.success('Approval submitted successfully');
    } catch (err) {
      toast.error('Failed to approve patch');
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async (id, comment) => {
    if (!comment) {
      toast.warning('Please provide a rejection reason');
      return;
    }
    setActionLoading(true);
    try {
      await rejectApproval(id, comment);
      setApprovals((prev) =>
        prev.map((a) =>
          a.id === id ? { ...a, status: 'rejected', rejectedBy: 'reviewer@aenealabs.com', rejectionReason: comment } : a
        )
      );
      setSelectedApproval(null);
      toast.success('Patch rejected');
    } catch (err) {
      toast.error('Failed to reject patch');
    } finally {
      setActionLoading(false);
    }
  };

  const handleRequestChanges = async (id, comment) => {
    if (!comment) {
      toast.warning('Please provide details for requested changes');
      return;
    }
    setActionLoading(true);
    try {
      await requestChanges(id, comment);
      toast.info(`Changes requested for approval ${id}`);
      setSelectedApproval(null);
    } catch (err) {
      toast.error('Failed to request changes');
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return <PageSkeleton />;
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Error Banner */}
      {error && (
        <div className="bg-critical-50 dark:bg-critical-900/30 border-b border-critical-200 dark:border-critical-800 p-4 flex items-center justify-between">
          <div className="flex items-center gap-2 text-critical-700 dark:text-critical-400">
            <ExclamationTriangleIcon className="w-5 h-5" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-critical-700 dark:text-critical-400 hover:text-critical-900">
            Dismiss
          </button>
        </div>
      )}

      {/* Header */}
      <header className="p-6 bg-white dark:bg-surface-800 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-aura-100 dark:bg-aura-900/30 rounded-lg">
              <ShieldCheckIcon className="w-6 h-6 text-aura-600 dark:text-aura-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">
                HITL Approvals
              </h1>
              <p className="text-surface-500 dark:text-surface-400">
                Review and approve security patches for deployment
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="flex items-center gap-2 px-4 py-2 text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors disabled:opacity-50"
            >
              <ArrowPathIcon className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
              Refresh
            </button>
            {statusCounts.pending > 0 && (
              <div className="flex items-center gap-2 px-3 py-1.5 bg-warning-50 dark:bg-warning-900/30 rounded-lg">
                <ExclamationTriangleIcon className="w-5 h-5 text-warning-500" />
                <span className="text-sm font-medium text-warning-700 dark:text-warning-400">
                  {statusCounts.pending} pending
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Search and Filters */}
        <div className="flex gap-4 flex-wrap">
          <div className="relative flex-1 max-w-md">
            <MagnifyingGlassIcon className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-surface-400" />
            <input
              type="text"
              placeholder="Search by title, CVE, or file..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
            />
          </div>
          <div className="flex gap-2 flex-wrap">
            {[
              { key: 'all', label: 'All' },
              { key: 'pending', label: 'Pending' },
              { key: 'sandbox_testing', label: 'Testing' },
              { key: 'approved', label: 'Approved' },
              { key: 'rejected', label: 'Rejected' },
            ].map((status) => (
              <button
                key={status.key}
                onClick={() => setFilter(status.key)}
                className={`
                  px-3 py-2 text-sm font-medium rounded-lg transition-all duration-200
                  ${filter === status.key
                    ? 'bg-aura-500 text-white shadow-sm'
                    : 'bg-surface-100 dark:bg-surface-700 text-surface-700 dark:text-surface-300 hover:bg-surface-200 dark:hover:bg-surface-600'
                  }
                `}
              >
                {status.label}
                <span className={`ml-1.5 ${filter === status.key ? 'text-aura-100' : 'text-surface-400'}`}>
                  ({statusCounts[status.key]})
                </span>
              </button>
            ))}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden p-6 pb-24 gap-6">
        {/* Approval List */}
        <div className="w-[400px] flex-shrink-0 overflow-y-auto space-y-3 pr-2">
          {filteredApprovals.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-surface-400">
              <FunnelIcon className="w-12 h-12 mb-3" />
              <p className="text-lg font-medium">No approvals match your filters</p>
            </div>
          ) : (
            filteredApprovals.map((approval) => (
              <ApprovalCard
                key={approval.id}
                approval={approval}
                isSelected={selectedApproval?.id === approval.id}
                onClick={() => setSelectedApproval(
                  selectedApproval?.id === approval.id ? null : approval
                )}
              />
            ))
          )}
        </div>

        {/* Detail Panel */}
        <ApprovalDetailPanel
          approval={selectedApproval}
          onApprove={handleApprove}
          onReject={handleReject}
          onRequestChanges={handleRequestChanges}
          isLoading={actionLoading}
        />
      </div>
    </div>
  );
}
