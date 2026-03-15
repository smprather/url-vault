from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from url_vault.cli import main


def test_cli_passes_once_flag_and_config_path() -> None:
    runner = CliRunner()

    with patch("url_vault.cli.run", return_value=0) as run_mock:
        result = runner.invoke(main, ["--config", "custom.yaml", "--once"])

    assert result.exit_code == 0
    run_mock.assert_called_once_with(config_path=Path("custom.yaml"), once=True)


def test_cli_help_includes_once_option() -> None:
    runner = CliRunner()

    result = runner.invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "--once" in result.output
