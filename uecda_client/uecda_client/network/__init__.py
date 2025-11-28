"""Network module for UECda client."""

from uecda_client.network.connection import GameConnection
from uecda_client.network.protocol import TableArray

__all__ = ["GameConnection", "TableArray"]
