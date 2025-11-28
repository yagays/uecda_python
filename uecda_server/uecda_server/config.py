"""Configuration management."""

from pathlib import Path

import yaml
from pydantic import BaseModel


class ServerConfig(BaseModel):
    """Server configuration."""

    host: str = "0.0.0.0"
    port: int = 42485
    protocol_version: int = 20070


class GameConfig(BaseModel):
    """Game configuration."""

    num_games: int = 100
    num_players: int = 5


class RulesConfig(BaseModel):
    """Rules configuration."""

    # Required rules
    revolution: bool = True
    eight_stop: bool = True
    lock: bool = True
    card_exchange: bool = True
    spade3_joker: bool = True
    sennichite: bool = True

    # Optional rules
    eleven_back: bool = False
    five_skip: bool = False
    six_reverse: bool = False
    seat_change: bool = False
    seat_change_interval: int = 3


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = "INFO"
    show_hands: bool = False


class Config(BaseModel):
    """Root configuration."""

    server: ServerConfig = ServerConfig()
    game: GameConfig = GameConfig()
    rules: RulesConfig = RulesConfig()
    logging: LoggingConfig = LoggingConfig()


def load_config(path: Path | str | None = None) -> Config:
    """Load configuration from YAML file.

    Args:
        path: Path to config file. If None, uses default config.

    Returns:
        Config object.
    """
    if path is None:
        return Config()

    config_path = Path(path)
    if not config_path.exists():
        return Config()

    with open(config_path) as f:
        data = yaml.safe_load(f)

    return Config(**data) if data else Config()
