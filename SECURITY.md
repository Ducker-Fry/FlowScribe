# Security Policy

## Supported Versions

FlowScribe is early-stage software. Security fixes are expected to target the latest released version.

| Version | Supported |
| --- | --- |
| 0.1.x | Yes |

## Reporting a Vulnerability

Please do not disclose security issues in public issues.

If you discover a vulnerability, report it privately to the project owner through GitHub. If GitHub private vulnerability reporting is enabled for this repository, use that channel. Otherwise, contact the maintainer through their GitHub profile and provide a minimal, responsible description of the issue.

Please include:

- Affected version or commit.
- Operating system.
- Steps to reproduce.
- Potential impact.
- Whether the issue involves local files, model downloads, release packaging, or credentials.

## Security Boundaries

FlowScribe is designed as a local-first tool:

- It should not upload user media by default.
- It should not collect telemetry by default.
- It should not bypass DRM or protected media controls.
- It should not require API keys for local transcription.

Future features involving external APIs, system audio capture, or GUI workflows should document their privacy and security implications before release.
