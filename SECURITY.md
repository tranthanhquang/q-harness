# Security Policy

## Supported Scope

Q-Harness 0.1.0 is an early MVP. Security fixes target the current development
version; no older release support or response-time guarantee is established.
Use it locally with repositories and operators you trust.

The intended boundary is a loopback HTTP/MCP service bound to one Project, token
authentication, explicit coding approval, path containment and Docker execution.
Keep the Docker daemon private. Do not expose the service directly to the Internet.
Task cancellation does not undo source changes.

## Report A Vulnerability

Use the repository's GitHub **Security → Report a vulnerability** private reporting
feature when enabled. Include affected version, reproduction steps, expected
boundary, actual impact and redacted logs. Avoid production secrets and private
source; a small synthetic reproduction is preferable.

If private reporting is unavailable, open a public issue asking only for a private
contact channel. Do not include exploit details, credentials or sensitive files
until a private channel is available. No dedicated security email is configured
in this source tree.

If a token/key was exposed, revoke it and rotate it through the issuing service.
Changing a committed file does not remove secrets from Git history.

## Known Operational Limits

- The Docker daemon is a privileged host capability; do not mount its socket into
  execution containers or expose it remotely.
- Backups can contain private project metadata and reports; snapshots are not
  encrypted. Restrict access and protect them independently.
- Dependency metadata review is not a vulnerability scan. Binary/container release
  obligations are recorded in [dependency review](docs/dependency-review.md).
- Outstanding platform/provider checks are listed in [verification](docs/verification.md).
