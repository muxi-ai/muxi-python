# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this SDK, please report it responsibly.

**Do NOT open a public GitHub issue.**

Instead, email **security@muxi.org** with:
- A description of the vulnerability
- Steps to reproduce
- Affected versions

We will acknowledge receipt within 48 hours and aim to provide a fix within 7 days for critical issues.

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest  | Yes       |

## Security Practices

- All GitHub Actions are pinned to SHA hashes
- Dependabot monitors dependencies weekly
- HMAC signatures use constant-time comparison
- No secrets are logged, even in debug mode
