# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly.

**Do not open a public GitHub issue for security vulnerabilities.**

Instead, use GitHub's [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability) feature on this repository.

### What to include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Response timeline

- **Acknowledgment**: within 48 hours
- **Initial assessment**: within 1 week
- **Fix or mitigation**: depends on severity; critical issues targeted within 2 weeks

## Security Model

This project handles sensitive email data. Key security properties:

1. **Read-only by default** — write operations must be explicitly enabled
2. **No email sending** — only draft creation is supported
3. **Restrictive file permissions** — token files stored with `600` permissions; environment variables supported for containerized deployments
4. **Prompt injection defense** — untrusted email content wrapped in XML delimiters
5. **Header injection prevention** — newlines rejected in email header fields
6. **Minimal OAuth scopes** — only `gmail.readonly`, `gmail.compose`, `gmail.labels`, and `gmail.modify`; never `https://mail.google.com/`
7. **Error isolation** — internal errors logged to stderr; only safe messages returned to the AI
8. **Audit logging** — all tool invocations are logged

If you believe any of these properties can be bypassed, that constitutes a security vulnerability.
