"""TCP server for UECda game."""

import logging
import socket
from typing import Callable

from uecda_server.models.card import CardSet
from uecda_server.models.player import Player

from .protocol import (
    TABLE_BYTES,
    TableArray,
    bytes_to_int,
    int_to_bytes,
    parse_profile_table,
)

logger = logging.getLogger(__name__)

# Response codes
ACCEPT = 9  # Card submission accepted
REJECT = 8  # Card submission rejected (pass)

# Game end codes
GAME_CONTINUE = 0
GAME_END = 1  # One game ended
ALL_GAMES_END = 2  # All games ended

# Timeout for protocol version detection (seconds)
HANDSHAKE_TIMEOUT = 2.5


class GameServer:
    """TCP server for hosting UECda games."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 42485,
        num_players: int = 5,
    ):
        """Initialize server.

        Args:
            host: Host address to bind to
            port: Port number
            num_players: Number of players (default 5)
        """
        self.host = host
        self.port = port
        self.num_players = num_players

        self._socket: socket.socket | None = None
        self._players: list[Player] = []

    @property
    def players(self) -> list[Player]:
        """Get connected players."""
        return self._players

    def start(self) -> None:
        """Start the server and listen for connections."""
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((self.host, self.port))
        self._socket.listen(1)
        logger.info(f"Server listening on {self.host}:{self.port}")

    def accept_players(
        self,
        on_connect: Callable[[int, str], None] | None = None,
    ) -> list[Player]:
        """Accept connections from all players.

        Args:
            on_connect: Callback when player connects (player_id, name)

        Returns:
            List of connected players
        """
        if self._socket is None:
            raise RuntimeError("Server not started")

        self._players = []

        for player_id in range(self.num_players):
            logger.info(f"Waiting for player {player_id}...")

            conn, addr = self._socket.accept()
            logger.info(f"Connection from {addr}")

            # Perform handshake
            player = self._handshake(conn, player_id)
            self._players.append(player)

            # Send player number
            self.send_int(player, player_id)

            if on_connect:
                on_connect(player_id, player.name)

            logger.info(f"Player {player_id}: {player.name} (protocol {player.protocol_version})")

        return self._players

    def _handshake(self, conn: socket.socket, player_id: int) -> Player:
        """Perform protocol handshake with client.

        Args:
            conn: Client socket
            player_id: Assigned player ID

        Returns:
            Player object
        """
        # Set timeout for protocol version detection
        conn.settimeout(HANDSHAKE_TIMEOUT)

        try:
            # Try to receive profile table
            data = self._recv_exact(conn, TABLE_BYTES)
            table = TableArray.from_bytes(data)
            protocol_version, name = parse_profile_table(table)
        except (socket.timeout, TimeoutError):
            # Old protocol - no profile sent
            protocol_version = 20060
            name = f"Player{player_id}"

        # Reset to blocking mode
        conn.settimeout(None)

        return Player(
            player_id=player_id,
            name=name[:14] if name else f"Player{player_id}",
            socket=conn,
            protocol_version=protocol_version,
            seat=player_id,
        )

    def _recv_exact(self, conn: socket.socket, size: int) -> bytes:
        """Receive exactly the specified number of bytes.

        Args:
            conn: Socket connection
            size: Number of bytes to receive

        Returns:
            Received bytes
        """
        data = bytearray()
        while len(data) < size:
            chunk = conn.recv(size - len(data))
            if not chunk:
                raise ConnectionError("Connection closed")
            data.extend(chunk)
        return bytes(data)

    def send_table(self, player: Player, table: TableArray) -> None:
        """Send table array to player.

        Args:
            player: Target player
            table: Table to send
        """
        if player.socket is None:
            raise RuntimeError(f"Player {player.player_id} not connected")

        data = table.to_bytes()
        player.socket.sendall(data)

    def recv_table(self, player: Player) -> TableArray:
        """Receive table array from player.

        Args:
            player: Source player

        Returns:
            Received table
        """
        if player.socket is None:
            raise RuntimeError(f"Player {player.player_id} not connected")

        data = self._recv_exact(player.socket, TABLE_BYTES)
        return TableArray.from_bytes(data)

    def send_int(self, player: Player, value: int) -> None:
        """Send integer to player.

        Args:
            player: Target player
            value: Integer value
        """
        if player.socket is None:
            raise RuntimeError(f"Player {player.player_id} not connected")

        data = int_to_bytes(value)
        player.socket.sendall(data)

    def recv_int(self, player: Player) -> int:
        """Receive integer from player.

        Args:
            player: Source player

        Returns:
            Received integer
        """
        if player.socket is None:
            raise RuntimeError(f"Player {player.player_id} not connected")

        data = self._recv_exact(player.socket, 4)
        return bytes_to_int(data)

    def broadcast_table(self, table: TableArray) -> None:
        """Send table to all players.

        Args:
            table: Table to send
        """
        for player in self._players:
            self.send_table(player, table)

    def send_hand_info(
        self,
        player: Player,
        hand: CardSet,
        game_state: "GameState",
        all_players: list[Player],
        all_hands: list[CardSet],
        is_exchange_phase: bool = False,
        exchange_count: int = 0,
    ) -> None:
        """Send hand and game state info to a player.

        Args:
            player: Target player
            hand: Player's hand
            game_state: Current game state
            all_players: All players
            all_hands: All players' hands
            is_exchange_phase: Whether in exchange phase
            exchange_count: Cards to exchange
        """
        table = TableArray()
        table.set_cards(hand)
        table.set_game_state(
            game_state,
            all_players,
            all_hands,
            player.player_id,
            is_exchange_phase,
            exchange_count,
        )
        self.send_table(player, table)

    def send_field_info(self, player: Player, field_cards: CardSet) -> None:
        """Send field state to a player.

        Args:
            player: Target player
            field_cards: Cards on the field
        """
        table = TableArray()
        table.set_cards(field_cards)
        self.send_table(player, table)

    def send_accept(self, player: Player) -> None:
        """Send acceptance response."""
        self.send_int(player, ACCEPT)

    def send_reject(self, player: Player) -> None:
        """Send rejection response (pass)."""
        self.send_int(player, REJECT)

    def send_game_end(self, player: Player, all_games_end: bool = False) -> None:
        """Send game end signal.

        Args:
            player: Target player
            all_games_end: If True, all games are over
        """
        self.send_int(player, ALL_GAMES_END if all_games_end else GAME_END)

    def send_game_continue(self, player: Player) -> None:
        """Send game continue signal."""
        self.send_int(player, GAME_CONTINUE)

    def close(self) -> None:
        """Close all connections and the server socket."""
        for player in self._players:
            if player.socket:
                try:
                    player.socket.close()
                except Exception:
                    pass
                player.socket = None

        if self._socket:
            self._socket.close()
            self._socket = None

        self._players = []
        logger.info("Server closed")

    def __enter__(self) -> "GameServer":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


# Import for type hints
from uecda_server.models.game_state import GameState  # noqa: E402
