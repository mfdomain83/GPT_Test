# Step Orchestrator

This repository contains `step_orchestrator.py`, a self-contained Python 3
script that lets you configure and run sequences of steps from a JSON
configuration file. Steps can be executed in their configured order, in any
custom order you provide at runtime, or skipped entirely.

## Requirements

* Python 3.8 or newer (only the standard library is used)

## Getting started

1. Make the script executable (optional) and generate a starter configuration:

   ```bash
   chmod +x step_orchestrator.py
   ./step_orchestrator.py generate-config steps.json
   ```

2. Inspect the generated `steps.json` file to review or customize the steps.
   Each step requires an `id` and a `command`; descriptions are optional.

3. List the available steps:

   ```bash
   ./step_orchestrator.py list --config steps.json
   ```

4. Run all configured steps in order:

   ```bash
   ./step_orchestrator.py run --config steps.json
   ```

5. Run a subset of steps in a custom order, skip steps, or perform a dry-run:

   ```bash
   # Run only the selected steps in the given order
   ./step_orchestrator.py run --config steps.json say-hello show-date

   # Skip a step even if it appears in the configuration order
   ./step_orchestrator.py run --config steps.json --skip show-date

   # Print the commands without executing them
   ./step_orchestrator.py run --config steps.json --dry-run
   ```

For detailed usage information, run `./step_orchestrator.py --help`.
