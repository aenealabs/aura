/**
 * Project Aura - File API Service
 *
 * Client-side service for file operations within the Knowledge Graph.
 * Handles file content retrieval, metadata, search, and references.
 *
 * Integrates with the GraphRAG backend for code entity navigation.
 */

import { apiClient } from './api';

// API endpoints for file operations
const ENDPOINTS = {
  FILE_CONTENT: '/files/content',
  FILE_METADATA: '/files/metadata',
  FILE_SEARCH: '/files/search',
  FILE_REFERENCES: '/files/references',
  FILE_SYMBOLS: '/files/symbols',
  FILE_HIGHLIGHTS: '/files/highlights',
};

/**
 * Custom error class for File API errors
 */
export class FileApiError extends Error {
  constructor(message, status, details = null) {
    super(message);
    this.name = 'FileApiError';
    this.status = status;
    this.details = details;
  }
}

// ============================================================================
// File Content Operations
// ============================================================================

/**
 * Get file content with optional line range
 *
 * @param {string} repositoryId - Repository ID
 * @param {string} filePath - Path to file within repository
 * @param {Object} [options] - Optional parameters
 * @param {string} [options.branch='main'] - Git branch
 * @param {number} [options.startLine] - Start line (1-indexed)
 * @param {number} [options.endLine] - End line (1-indexed)
 * @returns {Promise<{content: string, metadata: Object}>}
 */
export async function getFileContent(repositoryId, filePath, options = {}) {
  const params = new URLSearchParams();
  params.append('repository_id', repositoryId);
  params.append('path', filePath);

  if (options.branch) params.append('branch', options.branch);
  if (options.startLine) params.append('start_line', options.startLine);
  if (options.endLine) params.append('end_line', options.endLine);

  const { data } = await apiClient.get(`${ENDPOINTS.FILE_CONTENT}?${params.toString()}`);
  return data;
}

/**
 * Get file metadata (size, language, last modified, etc.)
 *
 * @param {string} repositoryId - Repository ID
 * @param {string} filePath - Path to file within repository
 * @param {string} [branch='main'] - Git branch
 * @returns {Promise<Object>} File metadata
 */
export async function getFileMetadata(repositoryId, filePath, branch = 'main') {
  const params = new URLSearchParams({
    repository_id: repositoryId,
    path: filePath,
    branch,
  });

  const { data } = await apiClient.get(`${ENDPOINTS.FILE_METADATA}?${params.toString()}`);
  return data;
}

// ============================================================================
// Search Operations
// ============================================================================

/**
 * Search within a file
 *
 * @param {string} repositoryId - Repository ID
 * @param {string} filePath - Path to file within repository
 * @param {string} query - Search query (supports regex)
 * @param {Object} [options] - Search options
 * @param {boolean} [options.caseSensitive=false] - Case sensitive search
 * @param {boolean} [options.regex=false] - Treat query as regex
 * @param {boolean} [options.wholeWord=false] - Match whole words only
 * @returns {Promise<Array<{line: number, content: string, matches: Array}>>}
 */
export async function searchInFile(repositoryId, filePath, query, options = {}) {
  const { data } = await apiClient.post(ENDPOINTS.FILE_SEARCH, {
    repository_id: repositoryId,
    path: filePath,
    query,
    case_sensitive: options.caseSensitive || false,
    regex: options.regex || false,
    whole_word: options.wholeWord || false,
  });
  return data;
}

/**
 * Search across files in repository
 *
 * @param {string} repositoryId - Repository ID
 * @param {string} query - Search query
 * @param {Object} [options] - Search options
 * @param {string[]} [options.filePatterns] - File patterns to include (e.g., ['*.py', '*.js'])
 * @param {string[]} [options.excludePatterns] - Patterns to exclude
 * @param {number} [options.maxResults=100] - Maximum results
 * @returns {Promise<Array<{filePath: string, line: number, content: string}>>}
 */
export async function searchInRepository(repositoryId, query, options = {}) {
  const { data } = await apiClient.post(`${ENDPOINTS.FILE_SEARCH}/repository`, {
    repository_id: repositoryId,
    query,
    file_patterns: options.filePatterns,
    exclude_patterns: options.excludePatterns,
    max_results: options.maxResults || 100,
  });
  return data;
}

// ============================================================================
// Reference Operations
// ============================================================================

/**
 * Get references to a symbol (function, class, variable)
 *
 * @param {string} repositoryId - Repository ID
 * @param {string} filePath - File containing the symbol
 * @param {string} symbolName - Name of the symbol
 * @param {Object} [options] - Options
 * @param {number} [options.line] - Line number of symbol definition
 * @param {string} [options.symbolType] - Type of symbol (function, class, variable)
 * @returns {Promise<Array<{filePath: string, line: number, type: string}>>}
 */
export async function getFileReferences(repositoryId, filePath, symbolName, options = {}) {
  const { data } = await apiClient.post(ENDPOINTS.FILE_REFERENCES, {
    repository_id: repositoryId,
    path: filePath,
    symbol_name: symbolName,
    line: options.line,
    symbol_type: options.symbolType,
  });
  return data;
}

/**
 * Get all symbols defined in a file
 *
 * @param {string} repositoryId - Repository ID
 * @param {string} filePath - Path to file
 * @returns {Promise<Array<{name: string, type: string, line: number, endLine: number}>>}
 */
export async function getFileSymbols(repositoryId, filePath) {
  const params = new URLSearchParams({
    repository_id: repositoryId,
    path: filePath,
  });

  const { data } = await apiClient.get(`${ENDPOINTS.FILE_SYMBOLS}?${params.toString()}`);
  return data;
}

/**
 * Get import/dependency graph for a file
 *
 * @param {string} repositoryId - Repository ID
 * @param {string} filePath - Path to file
 * @param {Object} [options] - Options
 * @param {number} [options.depth=1] - How many levels of dependencies to fetch
 * @param {string} [options.direction='both'] - 'imports', 'importedBy', or 'both'
 * @returns {Promise<{imports: Array, importedBy: Array}>}
 */
export async function getFileDependencies(repositoryId, filePath, options = {}) {
  const params = new URLSearchParams({
    repository_id: repositoryId,
    path: filePath,
    depth: options.depth || 1,
    direction: options.direction || 'both',
  });

  const { data } = await apiClient.get(`${ENDPOINTS.FILE_REFERENCES}/dependencies?${params.toString()}`);
  return data;
}

// ============================================================================
// Syntax Highlighting
// ============================================================================

/**
 * Get syntax highlighting tokens for a file
 *
 * @param {string} repositoryId - Repository ID
 * @param {string} filePath - Path to file
 * @param {Object} [options] - Options
 * @param {number} [options.startLine] - Start line
 * @param {number} [options.endLine] - End line
 * @returns {Promise<Array<{line: number, tokens: Array}>>}
 */
export async function getFileHighlights(repositoryId, filePath, options = {}) {
  const params = new URLSearchParams({
    repository_id: repositoryId,
    path: filePath,
  });

  if (options.startLine) params.append('start_line', options.startLine);
  if (options.endLine) params.append('end_line', options.endLine);

  const { data } = await apiClient.get(`${ENDPOINTS.FILE_HIGHLIGHTS}?${params.toString()}`);
  return data;
}

// ============================================================================
// Language Detection & Configuration
// ============================================================================

/**
 * Language configuration for syntax highlighting
 */
export const LANGUAGE_CONFIG = {
  python: {
    name: 'Python',
    extensions: ['.py', '.pyw', '.pyi'],
    mimeType: 'text/x-python',
    icon: 'py',
    color: '#3776AB',
    prismLanguage: 'python',
  },
  javascript: {
    name: 'JavaScript',
    extensions: ['.js', '.mjs', '.cjs'],
    mimeType: 'text/javascript',
    icon: 'js',
    color: '#F7DF1E',
    prismLanguage: 'javascript',
  },
  typescript: {
    name: 'TypeScript',
    extensions: ['.ts', '.tsx'],
    mimeType: 'text/typescript',
    icon: 'ts',
    color: '#3178C6',
    prismLanguage: 'typescript',
  },
  jsx: {
    name: 'JSX',
    extensions: ['.jsx'],
    mimeType: 'text/jsx',
    icon: 'jsx',
    color: '#61DAFB',
    prismLanguage: 'jsx',
  },
  java: {
    name: 'Java',
    extensions: ['.java'],
    mimeType: 'text/x-java',
    icon: 'java',
    color: '#B07219',
    prismLanguage: 'java',
  },
  go: {
    name: 'Go',
    extensions: ['.go'],
    mimeType: 'text/x-go',
    icon: 'go',
    color: '#00ADD8',
    prismLanguage: 'go',
  },
  rust: {
    name: 'Rust',
    extensions: ['.rs'],
    mimeType: 'text/x-rust',
    icon: 'rs',
    color: '#DEA584',
    prismLanguage: 'rust',
  },
  csharp: {
    name: 'C#',
    extensions: ['.cs'],
    mimeType: 'text/x-csharp',
    icon: 'cs',
    color: '#178600',
    prismLanguage: 'csharp',
  },
  cpp: {
    name: 'C++',
    extensions: ['.cpp', '.cc', '.cxx', '.hpp', '.h'],
    mimeType: 'text/x-c++src',
    icon: 'cpp',
    color: '#00599C',
    prismLanguage: 'cpp',
  },
  ruby: {
    name: 'Ruby',
    extensions: ['.rb', '.erb'],
    mimeType: 'text/x-ruby',
    icon: 'rb',
    color: '#CC342D',
    prismLanguage: 'ruby',
  },
  php: {
    name: 'PHP',
    extensions: ['.php'],
    mimeType: 'text/x-php',
    icon: 'php',
    color: '#777BB4',
    prismLanguage: 'php',
  },
  yaml: {
    name: 'YAML',
    extensions: ['.yml', '.yaml'],
    mimeType: 'text/yaml',
    icon: 'yaml',
    color: '#CB171E',
    prismLanguage: 'yaml',
  },
  json: {
    name: 'JSON',
    extensions: ['.json'],
    mimeType: 'application/json',
    icon: 'json',
    color: '#292929',
    prismLanguage: 'json',
  },
  markdown: {
    name: 'Markdown',
    extensions: ['.md', '.markdown'],
    mimeType: 'text/markdown',
    icon: 'md',
    color: '#083FA1',
    prismLanguage: 'markdown',
  },
  html: {
    name: 'HTML',
    extensions: ['.html', '.htm'],
    mimeType: 'text/html',
    icon: 'html',
    color: '#E34F26',
    prismLanguage: 'html',
  },
  css: {
    name: 'CSS',
    extensions: ['.css'],
    mimeType: 'text/css',
    icon: 'css',
    color: '#1572B6',
    prismLanguage: 'css',
  },
  sql: {
    name: 'SQL',
    extensions: ['.sql'],
    mimeType: 'text/x-sql',
    icon: 'sql',
    color: '#336791',
    prismLanguage: 'sql',
  },
  shell: {
    name: 'Shell',
    extensions: ['.sh', '.bash', '.zsh'],
    mimeType: 'text/x-shellscript',
    icon: 'sh',
    color: '#89E051',
    prismLanguage: 'bash',
  },
  dockerfile: {
    name: 'Dockerfile',
    extensions: ['Dockerfile'],
    mimeType: 'text/x-dockerfile',
    icon: 'docker',
    color: '#2496ED',
    prismLanguage: 'docker',
  },
  terraform: {
    name: 'Terraform',
    extensions: ['.tf', '.tfvars'],
    mimeType: 'text/x-terraform',
    icon: 'tf',
    color: '#7B42BC',
    prismLanguage: 'hcl',
  },
};

/**
 * Detect language from file path
 *
 * @param {string} filePath - File path
 * @returns {Object|null} Language configuration or null
 */
export function detectLanguage(filePath) {
  if (!filePath) return null;

  const fileName = filePath.split('/').pop();
  const extension = fileName.includes('.') ? '.' + fileName.split('.').pop().toLowerCase() : fileName;

  // Check for special filenames (Dockerfile, etc.)
  for (const [key, config] of Object.entries(LANGUAGE_CONFIG)) {
    if (config.extensions.includes(fileName) || config.extensions.includes(extension)) {
      return { ...config, key };
    }
  }

  return null;
}

/**
 * Get Prism.js language identifier for a file
 *
 * @param {string} filePath - File path
 * @returns {string} Prism language identifier
 */
export function getPrismLanguage(filePath) {
  const lang = detectLanguage(filePath);
  return lang?.prismLanguage || 'plaintext';
}

// ============================================================================
// Mock Data for Development
// ============================================================================

/**
 * Generate mock file content for development
 * Used when API is not available
 */
export function getMockFileContent(filePath) {
  const mockFiles = {
    'src/auth/handlers/login.py': {
      content: `"""
Authentication login handler module.

Provides secure login functionality with input validation
and rate limiting protection.
"""

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, Request
from pydantic import BaseModel, EmailStr, validator

from ..models.user import User
from ..services.auth_service import AuthService
from ..utils.security import verify_password, create_access_token

logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    """Login request schema with validation."""

    email: EmailStr
    password: str
    remember_me: bool = False

    @validator('password')
    def password_not_empty(cls, v):
        if not v or len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v


class LoginResponse(BaseModel):
    """Login response with access token."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str


async def handle_login(
    request: Request,
    login_data: LoginRequest,
    auth_service: AuthService
) -> LoginResponse:
    """
    Handle user login with security checks.

    Args:
        request: FastAPI request object
        login_data: Validated login credentials
        auth_service: Authentication service instance

    Returns:
        LoginResponse with access token

    Raises:
        HTTPException: On authentication failure
    """
    # Check rate limiting
    client_ip = request.client.host
    if await auth_service.is_rate_limited(client_ip):
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Please try again later."
        )

    # Attempt authentication
    user = await auth_service.authenticate(
        email=login_data.email,
        password=login_data.password
    )

    if not user:
        # Log failed attempt
        await auth_service.record_failed_attempt(client_ip)
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    # Generate access token
    expires_delta = timedelta(days=7 if login_data.remember_me else 1)
    access_token = create_access_token(
        data={"sub": user.id, "email": user.email},
        expires_delta=expires_delta
    )

    logger.info(f"Successful login for user: {user.email}")

    return LoginResponse(
        access_token=access_token,
        expires_in=int(expires_delta.total_seconds()),
        user_id=user.id
    )
`,
      metadata: {
        language: 'python',
        size: 2847,
        lines: 95,
        lastModified: '2024-12-15T14:30:00Z',
        encoding: 'utf-8',
      },
    },
    'src/api/routes/users.js': {
      content: `/**
 * User Routes Module
 *
 * RESTful API endpoints for user management.
 * Includes authentication middleware and input validation.
 */

import express from 'express';
import { body, param, query, validationResult } from 'express-validator';
import { authenticate, authorize } from '../middleware/auth.js';
import { UserService } from '../services/UserService.js';
import { logger } from '../utils/logger.js';

const router = express.Router();
const userService = new UserService();

/**
 * Validation middleware
 */
const handleValidation = (req, res, next) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    return res.status(400).json({ errors: errors.array() });
  }
  next();
};

/**
 * GET /users
 * List all users with pagination
 */
router.get('/',
  authenticate,
  authorize(['admin', 'manager']),
  [
    query('page').optional().isInt({ min: 1 }).toInt(),
    query('limit').optional().isInt({ min: 1, max: 100 }).toInt(),
    query('sort').optional().isIn(['name', 'email', 'createdAt']),
  ],
  handleValidation,
  async (req, res, next) => {
    try {
      const { page = 1, limit = 20, sort = 'createdAt' } = req.query;

      const result = await userService.listUsers({
        page,
        limit,
        sort,
        organizationId: req.user.organizationId,
      });

      res.json(result);
    } catch (error) {
      next(error);
    }
  }
);

/**
 * GET /users/:id
 * Get user by ID
 */
router.get('/:id',
  authenticate,
  param('id').isUUID(),
  handleValidation,
  async (req, res, next) => {
    try {
      const user = await userService.getUserById(req.params.id);

      if (!user) {
        return res.status(404).json({ error: 'User not found' });
      }

      // Check authorization
      if (user.id !== req.user.id && !req.user.roles.includes('admin')) {
        return res.status(403).json({ error: 'Forbidden' });
      }

      res.json(user);
    } catch (error) {
      next(error);
    }
  }
);

/**
 * POST /users
 * Create new user
 */
router.post('/',
  authenticate,
  authorize(['admin']),
  [
    body('email').isEmail().normalizeEmail(),
    body('name').trim().isLength({ min: 2, max: 100 }),
    body('role').isIn(['user', 'manager', 'admin']),
  ],
  handleValidation,
  async (req, res, next) => {
    try {
      const user = await userService.createUser({
        ...req.body,
        organizationId: req.user.organizationId,
        createdBy: req.user.id,
      });

      logger.info(\`User created: \${user.id}\`, { createdBy: req.user.id });

      res.status(201).json(user);
    } catch (error) {
      if (error.code === 'USER_EXISTS') {
        return res.status(409).json({ error: 'User already exists' });
      }
      next(error);
    }
  }
);

export default router;
`,
      metadata: {
        language: 'javascript',
        size: 2534,
        lines: 108,
        lastModified: '2024-12-14T09:15:00Z',
        encoding: 'utf-8',
      },
    },
  };

  const normalizedPath = filePath.replace(/^\/+/, '');
  return mockFiles[normalizedPath] || {
    content: `// File: ${filePath}\n// Content not available in mock data`,
    metadata: {
      language: detectLanguage(filePath)?.key || 'plaintext',
      size: 0,
      lines: 2,
      lastModified: new Date().toISOString(),
      encoding: 'utf-8',
    },
  };
}

// ============================================================================
// Default Export
// ============================================================================

export default {
  // Content
  getFileContent,
  getFileMetadata,
  // Search
  searchInFile,
  searchInRepository,
  // References
  getFileReferences,
  getFileSymbols,
  getFileDependencies,
  // Highlighting
  getFileHighlights,
  // Utils
  detectLanguage,
  getPrismLanguage,
  getMockFileContent,
  // Constants
  LANGUAGE_CONFIG,
};
