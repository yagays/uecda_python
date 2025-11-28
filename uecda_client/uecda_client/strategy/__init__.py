"""Strategy module for UECda client."""

from uecda_client.strategy.base import Strategy
from uecda_client.strategy.simple import SimpleStrategy

__all__ = ["Strategy", "SimpleStrategy"]
