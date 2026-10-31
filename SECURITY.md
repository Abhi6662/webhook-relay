# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in webhook-relay, please report it by:

1. **Do not** open a public issue
2. Email the maintainer or use GitHub's private vulnerability reporting feature
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will respond within 48 hours and work with you to address the issue promptly.

## Security Considerations

- webhook-relay verifies HMAC-SHA256 signatures on incoming webhooks
- Always use strong, unique webhook secrets per source
- The SQLite WAL queue stores webhook payloads locally - secure the database file
- Rate limiting is recommended in front of the service
- HMAC verification uses constant-time comparison to prevent timing attacks