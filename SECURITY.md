# Security Policy

## Supported versions

Only the latest release receives fixes.

## Threat model

Split My Music is designed for a personal computer, home network or NAS. **It has no authentication.** Do not expose it directly to the internet. If you must, use a reverse proxy with HTTPS and authentication, lower the upload limits, and read the README's privacy and security section.

Built-in protections: upload size and duration limits, extension and `ffprobe` validation, sanitized file names, no shell strings built from user data, results served only through job-checked URLs, bounded queue, disk-space guard, and no stack traces in responses.

## Reporting a vulnerability

Please use GitHub's **private vulnerability reporting** (Security tab, "Report a vulnerability"). Do not open public issues for security problems. You should get a first response within a few days.
