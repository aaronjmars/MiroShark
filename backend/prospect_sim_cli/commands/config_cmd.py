"""
`miroshark config` — manage CLI configuration.

Stores persistent settings in ~/.miroshark/config.json.
Supported keys: api_url, default_rounds, default_parallel.

Rule 1: non-interactive — all via flags/arguments.
Rule 10: `config show` returns data; `config set` returns nothing on success.
"""

from __future__ import annotations

from typing import Optional
from typing_extensions import Annotated

import typer

from ..cache import CliConfig
from ..output import print_error, print_json

app = typer.Typer(help="Manage CLI configuration (API URL, defaults).")

# Keys that are valid for `config set`
VALID_KEYS = {"api-url", "default-rounds", "default-parallel"}

# Map CLI key names (kebab-case) to config file keys (snake_case)
KEY_MAP = {
    "api-url": "api_url",
    "default-rounds": "default_rounds",
    "default-parallel": "default_parallel",
}


@app.command("show")
def config_show(
    quiet: Annotated[bool, typer.Option("--quiet")] = False,
) -> None:
    """
    Show current CLI configuration.

    Examples:
      miroshark config show
      miroshark config show --quiet | jq '.api_url'
    """
    config = CliConfig()
    data = config.all()

    if quiet:
        print_json(data)
    else:
        typer.echo("\nmiroshark configuration:")
        typer.echo(f"  Config file: ~/.miroshark/config.json")
        for k, v in data.items():
            typer.echo(f"  {k}: {v}")
        typer.echo()


@app.command("set")
def config_set(
    key: Annotated[str, typer.Argument(help=f"Config key. Valid: {', '.join(sorted(VALID_KEYS))}")],
    value: Annotated[str, typer.Argument(help="Value to set")],
) -> None:
    """
    Set a configuration value.

    Examples:
      miroshark config set api-url http://localhost:5001
      miroshark config set default-rounds 12
      miroshark config set default-parallel true
    """
    if key not in VALID_KEYS:
        print_error(
            "invalid_config_key",
            f"Unknown config key: {key}",
            fix=f"Valid keys: {', '.join(sorted(VALID_KEYS))}",
            exit_code=1,
        )

    config = CliConfig()
    config_key = KEY_MAP[key]

    # Coerce types
    coerced_value: object = value
    if config_key == "default_rounds":
        try:
            coerced_value = int(value)
        except ValueError:
            print_error("invalid_value", f"default-rounds must be an integer (got: {value!r})", exit_code=1)
    elif config_key == "default_parallel":
        if value.lower() in ("true", "1", "yes"):
            coerced_value = True
        elif value.lower() in ("false", "0", "no"):
            coerced_value = False
        else:
            print_error("invalid_value", f"default-parallel must be true/false (got: {value!r})", exit_code=1)

    config.set(config_key, coerced_value)
    # Rule 10: nothing on success


@app.command("reset")
def config_reset() -> None:
    """
    Reset all configuration to defaults.

    Examples:
      miroshark config reset
    """
    from ..cache import CONFIG_FILE
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
    # Rule 10: nothing on success
