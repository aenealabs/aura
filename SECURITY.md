# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Project Aura, please report it responsibly. **Do not open a public GitHub issue for security vulnerabilities.**

### How to Report

Email: **security@aenealabs.com**

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact assessment
- Any suggested fixes (optional)

### Response Timeline

| Action | Timeline |
|--------|----------|
| Acknowledgment of report | Within 48 hours |
| Initial assessment | Within 5 business days |
| Fix development | Based on severity |
| Public disclosure | After fix is deployed |

### Severity Classification

| Severity | Description | Target Resolution |
|----------|-------------|-------------------|
| Critical | Remote code execution, data breach, sandbox escape | 24-48 hours |
| High | Authentication bypass, privilege escalation, injection | 1-2 weeks |
| Medium | Information disclosure, CSRF, misconfiguration | 2-4 weeks |
| Low | Minor information leak, non-exploitable finding | Next release cycle |

### Scope

The following are in scope for security reports:
- Core platform services (`src/`)
- Agent orchestration and execution
- Sandbox isolation mechanisms
- Authentication and authorization
- GraphRAG data access controls
- Infrastructure-as-code templates (`deploy/`)
- Container images and configurations

### Out of Scope

- Vulnerabilities in third-party dependencies (report to upstream maintainers)
- Social engineering attacks
- Denial of service attacks
- Issues in archived code (`archive/` directory)

## Security Design Principles

Project Aura follows these security principles:

- **Defense in depth**: Multiple layers of security controls
- **Least privilege**: Minimal permissions for all components
- **Secure defaults**: Security-first configuration out of the box
- **Audit trail**: All actions logged for compliance
- **Isolation**: Sandboxed execution for untrusted code

See [Security Architecture](docs/support/architecture/security-architecture.md) for detailed technical controls.
