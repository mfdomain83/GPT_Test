#!/usr/bin/env python3
"""Configurable step orchestrator.

This script allows users to define a set of steps in a JSON configuration
file and then execute them in any order. Steps can be skipped entirely or run
in an arbitrary sequence. The script is self contained and does not require any
additional packages beyond the Python standard library.

Configuration structure
=======================

The configuration file is a JSON object with a single key, ``steps``. The value
of ``steps`` is a list of step objects. Each step object supports the following
fields:

``id`` (required)
    Unique identifier for the step.
``description`` (optional)
    Free form text shown when listing steps.
``command`` (required)
    Shell command to execute. The command can be either a string or a list of
    strings. When provided as a string the command is parsed using
    :func:`shlex.split` before execution.

Example configuration::

    {
      "steps": [
        {
          "id": "say-hello",
          "description": "Print a greeting",
          "command": "echo 'Hello there!'"
        },
        {
          "id": "python-example",
          "description": "Execute an inline Python snippet",
          "command": ["python", "-c", "print('This runs from the config!')"]
        }
      ]
    }

Usage
-----

Generate a starter configuration (will refuse to overwrite existing files)::

    ./step_orchestrator.py generate-config steps.json

List configured steps::

    ./step_orchestrator.py list --config steps.json

Run steps in configuration order::

    ./step_orchestrator.py run --config steps.json

Run selected steps (in the order provided)::

    ./step_orchestrator.py run --config steps.json say-hello python-example

Skip specific steps::

    ./step_orchestrator.py run --config steps.json --skip say-hello

Perform a dry-run that only prints the commands that would execute::

    ./step_orchestrator.py run --config steps.json --dry-run
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

DEFAULT_CONFIG = {
    "steps": [
        {
            "id": "say-hello",
            "description": "Print a greeting to the terminal",
            "command": "echo 'Hello from the orchestrator!'",
        },
        {
            "id": "show-date",
            "description": "Display the current date",
            "command": ["date"],
        },
    ]
}


class StepConfigError(RuntimeError):
    """Raised when the configuration file cannot be parsed."""


@dataclass(frozen=True)
class Step:
    """Represents an executable step from the configuration file."""

    id: str
    description: str
    command: Sequence[str]

    @staticmethod
    def from_dict(data: dict) -> "Step":
        try:
            step_id = data["id"]
            command = data["command"]
        except KeyError as exc:  # pragma: no cover - defensive programming
            raise StepConfigError(f"Missing required field: {exc.args[0]}") from exc

        if not isinstance(step_id, str) or not step_id:
            raise StepConfigError("Step 'id' must be a non-empty string")

        if isinstance(command, str):
            command_list: Sequence[str] = shlex.split(command)
        elif isinstance(command, Iterable):
            command_list = tuple(str(part) for part in command)
        else:  # pragma: no cover - defensive programming
            raise StepConfigError(
                "Step 'command' must be either a string or an iterable of strings"
            )

        description = str(data.get("description", ""))
        return Step(id=step_id, description=description, command=command_list)


class StepRunner:
    """Executes steps loaded from configuration."""

    def __init__(self, steps: Sequence[Step]):
        ids = [step.id for step in steps]
        duplicates = {step_id for step_id in ids if ids.count(step_id) > 1}
        if duplicates:
            joined = ", ".join(sorted(duplicates))
            raise StepConfigError(f"Duplicate step identifiers are not allowed: {joined}")
        self._steps_by_id = {step.id: step for step in steps}
        self._configured_order = [step.id for step in steps]

    def list_steps(self) -> Sequence[Step]:
        return [self._steps_by_id[step_id] for step_id in self._configured_order]

    def validate_step_ids(self, step_ids: Iterable[str]) -> None:
        unknown = [step_id for step_id in step_ids if step_id not in self._steps_by_id]
        if unknown:
            joined = ", ".join(sorted(unknown))
            raise StepConfigError(f"Unknown step id(s): {joined}")

    def run(
        self,
        step_ids: Sequence[str] | None = None,
        skip_ids: Sequence[str] | None = None,
        *,
        dry_run: bool = False,
    ) -> int:
        """Run steps and return the exit status.

        When *step_ids* is ``None`` the configured order is used. When provided,
        steps execute exactly in the order supplied by the user. Any steps listed
        in *skip_ids* are excluded from the run. The method returns the exit code
        from the first failing command or zero when all commands succeed.
        """

        step_ids = list(self._configured_order if step_ids is None else step_ids)
        skip_ids = set(skip_ids or [])
        self.validate_step_ids(step_ids)
        self.validate_step_ids(skip_ids)

        steps_to_run = [step_id for step_id in step_ids if step_id not in skip_ids]

        for step_id in steps_to_run:
            step = self._steps_by_id[step_id]
            print(f"\n>>> Running step '{step.id}'")
            if step.description:
                print(f"    {step.description}")
            print(f"    Command: {' '.join(step.command)}")
            if dry_run:
                continue

            try:
                completed = subprocess.run(step.command, check=False)
            except FileNotFoundError:
                print(f"Command not found: {step.command[0]}", file=sys.stderr)
                return 127

            if completed.returncode != 0:
                print(
                    f"Step '{step.id}' failed with exit code {completed.returncode}",
                    file=sys.stderr,
                )
                return completed.returncode

        return 0


def load_steps(config_path: Path) -> StepRunner:
    if not config_path.exists():
        raise StepConfigError(
            f"Configuration file '{config_path}' does not exist. "
            "Use the 'generate-config' command to create one."
        )

    with config_path.open("r", encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise StepConfigError(
                f"Failed to parse JSON configuration: {exc.msg}"
            ) from exc

    steps_data = data.get("steps")
    if not isinstance(steps_data, list) or not steps_data:
        raise StepConfigError("Configuration must define a non-empty 'steps' list")

    steps = [Step.from_dict(raw_step) for raw_step in steps_data]
    return StepRunner(steps)


def generate_config(path: Path) -> None:
    if path.exists():
        raise StepConfigError(f"Cannot overwrite existing file: {path}")
    with path.open("w", encoding="utf-8") as fh:
        json.dump(DEFAULT_CONFIG, fh, indent=2)
        fh.write("\n")
    print(f"Wrote example configuration to {path}")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.set_defaults(command=None)
    subparsers = parser.add_subparsers(dest="command")

    gen_parser = subparsers.add_parser(
        "generate-config", help="Create an example configuration file"
    )
    gen_parser.add_argument("path", type=Path, help="Path to write the config file")

    list_parser = subparsers.add_parser("list", help="List configured steps")
    list_parser.add_argument(
        "--config",
        type=Path,
        default=Path("steps.json"),
        help="Path to the configuration file (default: steps.json)",
    )

    run_parser = subparsers.add_parser("run", help="Run one or more steps")
    run_parser.add_argument(
        "--config",
        type=Path,
        default=Path("steps.json"),
        help="Path to the configuration file (default: steps.json)",
    )
    run_parser.add_argument(
        "steps",
        nargs="*",
        help="Optional list of step identifiers to run (defaults to config order)",
    )
    run_parser.add_argument(
        "--skip",
        nargs="*",
        default=(),
        help="Step identifiers to skip (applies to configured or explicit order)",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the commands without executing them",
    )

    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        parser.exit(1)
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    try:
        if args.command == "generate-config":
            generate_config(args.path)
            return 0

        runner = load_steps(args.config)
        if args.command == "list":
            for step in runner.list_steps():
                desc = f" - {step.description}" if step.description else ""
                print(f"{step.id}{desc}")
            return 0

        if args.command == "run":
            step_ids = args.steps if args.steps else None
            return runner.run(step_ids=step_ids, skip_ids=args.skip, dry_run=args.dry_run)

    except StepConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
