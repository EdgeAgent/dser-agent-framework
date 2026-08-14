# Security Policy

## Supported versions

Security fixes are applied to the latest `main` branch while the project is in its pre-1.0 stage.

## Reporting a vulnerability

Do not disclose suspected vulnerabilities in public issues. Report them privately to the repository owner with a concise description, affected component, reproduction steps, expected impact, and any proposed mitigation.

## Security scope

DSER helps applications reason about evidence provenance, memory conflicts, and action decisions. It does not make an application secure by itself. Integrators remain responsible for authentication, authorization, secret handling, encryption, network security, tool permissions, data retention, and human approval for high-impact actions.

Particularly relevant reports include methods that bypass reconciliation, poison retained memory, forge source metadata, cause unsafe action after verification failure, or cross user/tenant memory boundaries.
