# Contributing to DSER

Thank you for contributing to DSER. The framework’s purpose is to make evidence reconciliation explicit, testable, and auditable. Contributions should strengthen that contract rather than bypass it.

## Development workflow

1. Create a focused branch from `main`.
2. Install the project with `python3 -m pip install -e .`.
3. Add or update tests for every behavioral change.
4. Run `python3 -m unittest discover -s tests -v`.
5. Update the README or design documentation whenever public behavior changes.

## Design requirements

| Requirement | Contribution expectation |
| --- | --- |
| Provenance | New evidence types must preserve an attributable source or clearly state that provenance is unavailable. |
| Safety | New integrations must not bypass the reconciliation policy for consequential actions. |
| Determinism | Policy changes should be unit-testable with fixed inputs and clear dispositions. |
| Minimal retention | Memory adapters must support validation and useful-outcome filtering. |
| Provider independence | Core modules must not require a particular LLM, vector database, or hosted API. |

## Reporting vulnerabilities

Please do not open public issues for suspected security vulnerabilities. Follow the process in [SECURITY.md](SECURITY.md).
