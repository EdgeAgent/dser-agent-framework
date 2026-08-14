# Run DSER Locally: Browser Demo and Terminal CLI

DSER now includes two local interfaces built on the same deterministic decision runner. Neither interface requires an API key, external model, database, network integration, or side-effecting tool. They are designed to make evidence reconciliation visible before you connect DSER to a real agent stack.

| Interface | Best for | Command |
| --- | --- | --- |
| **Browser demo** | Exploring evidence, memory, conflict, and verification visually; demos and onboarding. | `dser-demo` |
| **Terminal CLI** | Fast experiments, shell scripts, CI, and prompt-driven scenario creation. | `dser-cli --scenario conflict` |

## Install from a local clone

```bash
git clone https://github.com/EdgeAgent/dser-agent-framework.git
cd dser-agent-framework
python3 -m pip install -e .
```

Editable installation exposes both commands. You can also run the modules directly with `python3 -m dser.web_demo` and `python3 -m dser.cli`.

## Browser demo: DSER Local Lab

Start the browser demo:

```bash
dser-demo
```

The server binds to `http://127.0.0.1:8765` by default and opens the local page in your default browser. Press `Ctrl+C` in the terminal to stop it.

```bash
# Use a different local port without opening a browser automatically.
dser-demo --port 9000 --no-browser
```

The demo page provides editable controls for task key, goal, risk, current observation, scoring inputs, optional memory, optional verifier response, and a safe local action. Every run shows the final disposition, selected claim, conflict set, score, verifier state, action result, and memory-retention result.

### Built-in browser scenarios

| Scenario | What it demonstrates | Expected result |
| --- | --- | --- |
| **Clean evidence** | A fresh, source-attributed system record with no conflict. | `ACT` |
| **Verified conflict** | A stale memory says `email`; current evidence and verifier say `sms`. | `ACT` after verification |
| **Missing provenance** | A consequential user claim lacks attributable support. | `ASK` |

The local page calls a same-origin in-process API only:

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/` | `GET` | Serves the local browser interface. |
| `/api/examples` | `GET` | Returns deterministic built-in scenarios. |
| `/api/run` | `POST` | Runs one in-memory DSER decision from a JSON payload. |

The server accepts request bodies up to 64 KiB, binds to loopback by default, and does not authenticate requests because it is a local development demo. Do not expose the demo to untrusted networks or use it as a production action service without adding authentication, authorization, input validation, audit storage, and your own deployment controls.

## Terminal CLI

Run a deterministic scenario with a readable summary:

```bash
dser-cli --scenario conflict
```

The default scenario is `conflict`. Available scenarios are `clean`, `conflict`, and `uncertain`.

```bash
# Print the full trace for scripts, tests, or inspection.
dser-cli --scenario clean --json

# Enter a custom decision interactively.
dser-cli --interactive
```

The interactive flow prompts for current observation data, risk, optional remembered evidence, optional verifier output, and whether to run the safe local action. Score inputs must be between `0` and `1`, and source/risk values must use their DSER serialized names such as `system_of_record` and `medium`.

### Example terminal output

```text
DSER disposition: ACT
Reason: An authoritative verification record resolved the material conflict.
Selected claim: customer.delivery_preference = sms (verification)
Conflicting evidence: sms (system_of_record), email (memory), sms (verification)
Action: Local demo action accepted customer.delivery_preference=sms.
Verification used: True
Memory written: True
```

## How the local runner maps to DSER

Both interfaces call `run_local_decision()` from `dser.local`. The helper creates a current `Claim`, optionally stores a deliberately older memory episode, optionally configures a deterministic `MappingVerifier`, and uses a standard `DSERAgent` with `ReconciliationPolicy` and `InMemoryStore`.

| Local input | DSER component |
| --- | --- |
| Current value, source, score inputs, provenance | `Claim` representing current observation |
| Remembered value and age | Retained `MemoryRecord` retrieved by `InMemoryStore` |
| Risk dropdown or CLI field | `AgentTask.risk` |
| Verified value | `Claim` returned by `MappingVerifier` |
| Run action toggle | `ActionResult` callback that runs only after `ACT` |

The action is intentionally a local message—not an email, database update, or external API call. Replace the reference adapters only after reviewing the [quickstart](quickstart.md), [API reference](api-reference.md), [architecture contract](design.md), and [security policy](../SECURITY.md).

## Validate locally

```bash
python3 -m unittest discover -s tests -v
python3 -m dser.cli --scenario clean --json
python3 -m dser.web_demo --help
```

For a repeatable end-to-end browser check, start the server with `--no-browser`, then request `http://127.0.0.1:8765/api/examples` and `POST` a scenario to `/api/run`.
