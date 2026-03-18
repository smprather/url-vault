from __future__ import annotations

from pathlib import Path

from url_vault.config import load_config


def test_e2e_self_config_loads_single_git_repo() -> None:
    config_path = Path("e2e/url-vault-self.yaml").resolve()

    config = load_config(config_path)
    git_items = [item for item in config.items if item.kind == "git"]

    assert config.destination_dir == (config_path.parent / "artifacts" / "cache").resolve()
    assert len(git_items) == 1
    assert git_items[0].url == "https://github.com/smprather/url-vault.git"
