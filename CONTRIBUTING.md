# Contributing to gmail-mcp

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/gmail-mcp.git`
3. Create a branch: `git checkout -b feature/your-feature-name`
4. Install in development mode: `pip install -e ".[dev]"`

## Development Guidelines

### Code Style

- We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting
- Target Python 3.11+
- Line length limit: 100 characters
- Run `ruff check src/` before submitting

### Security First

This project handles sensitive email data. All contributions must:

- **Never** introduce email sending capability — draft creation is the maximum write access
- **Never** write credentials or tokens to disk — use macOS Keychain via `keyring`
- **Always** wrap untrusted content (email bodies, subjects, sender names) in XML-style delimiters
- **Always** log tool invocations for audit purposes
- **Never** log full email content — only argument keys and metadata

### Commit Messages

- Use clear, concise commit messages
- Start with a verb: "Add", "Fix", "Update", "Remove"
- Reference issues when applicable: "Fix #42: handle expired OAuth tokens"

### Pull Requests

1. Keep PRs focused — one feature or fix per PR
2. Update documentation if your change affects user-facing behavior
3. Add tests for new functionality
4. Ensure all existing tests pass
5. Fill out the PR template

## Reporting Bugs

- Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md)
- Include steps to reproduce, expected behavior, and actual behavior
- **Never** include OAuth tokens, client secrets, or email content in bug reports

## Security Vulnerabilities

If you discover a security vulnerability, please **do not** open a public issue. Instead, see [SECURITY.md](SECURITY.md) for responsible disclosure instructions.

## Questions?

Open a [discussion](https://github.com/stackdev-opensource/gmail-mcp/discussions) for questions that aren't bug reports or feature requests.
