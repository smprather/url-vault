from __future__ import annotations

from pathlib import Path

import rich_click as click

from url_vault.app import run


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path, dir_okay=False),
    default=Path("config.yaml"),
    show_default=True,
    help="Path to the YAML config file.",
)
@click.option(
    "--once",
    is_flag=True,
    help="Run a single sync cycle and exit instead of entering the update loop.",
)
def main(config_path: Path, once: bool) -> None:
    """Mirror configured Git repositories and URLs into a local cache."""
    click.get_current_context().exit(run(config_path=config_path, once=once))
