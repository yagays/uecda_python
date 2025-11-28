"""TCP connection handling for UECda client.

Based on C implementation: tndhm_devkit_c-20221111/client/connection.c
"""

import logging
import socket

from uecda_client.network.protocol import (
    PROTOCOL_VERSION,
    TABLE_BYTES,
    TableArray,
    bytes_to_int,
    create_profile_table,
    int_to_bytes,
)

logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 42485


class GameConnection:
    """Manages TCP connection to UECda server.

    Corresponds to C implementation's connection.c functions:
    - openSocket/closeSocket
    - sendProfile (entryToGame)
    - refreshTable/sendTable
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        """Initialize connection parameters.

        Args:
            host: Server hostname or IP address
            port: Server port number
        """
        self.host = host
        self.port = port
        self._socket: socket.socket | None = None
        self._player_id: int = -1

    @property
    def player_id(self) -> int:
        """Get assigned player ID."""
        return self._player_id

    def connect(self) -> None:
        """Establish TCP connection to server.

        Corresponds to C: openSocket()
        """
        if self._socket is not None:
            raise RuntimeError("Already connected")

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect((self.host, self.port))
        logger.info(f"Connected to {self.host}:{self.port}")

    def close(self) -> None:
        """Close the connection.

        Corresponds to C: closeSocket()
        """
        if self._socket is not None:
            self._socket.close()
            self._socket = None
            logger.info("Connection closed")

    def send_profile(self, name: str) -> int:
        """Send player profile and receive player ID.

        Corresponds to C: entryToGame() -> sendProfile()

        Args:
            name: Player name (max 14 characters)

        Returns:
            Assigned player ID (0-4)
        """
        if self._socket is None:
            raise RuntimeError("Not connected")

        # Create and send profile table
        profile = create_profile_table(PROTOCOL_VERSION, name)
        self._send_table(profile)
        logger.debug(f"Sent profile: {name} (protocol: {PROTOCOL_VERSION})")

        # Receive player ID
        data = self._recv_exact(4)
        self._player_id = bytes_to_int(data)
        logger.info(f"Assigned player ID: {self._player_id}")

        return self._player_id

    def receive_table(self) -> TableArray:
        """Receive a table from server.

        Corresponds to C: refreshTable()

        Returns:
            Received TableArray
        """
        if self._socket is None:
            raise RuntimeError("Not connected")

        data = self._recv_exact(TABLE_BYTES)
        table = TableArray.from_bytes(data)
        logger.debug("Received table")
        return table

    def send_table(self, table: TableArray) -> None:
        """Send a table to server.

        Corresponds to C: sendTable()

        Args:
            table: TableArray to send
        """
        self._send_table(table)
        logger.debug("Sent table")

    def receive_int(self) -> int:
        """Receive a single integer from server.

        Returns:
            Received integer value
        """
        if self._socket is None:
            raise RuntimeError("Not connected")

        data = self._recv_exact(4)
        value = bytes_to_int(data)
        logger.debug(f"Received int: {value}")
        return value

    def send_int(self, value: int) -> None:
        """Send a single integer to server.

        Args:
            value: Integer to send
        """
        if self._socket is None:
            raise RuntimeError("Not connected")

        self._socket.sendall(int_to_bytes(value))
        logger.debug(f"Sent int: {value}")

    def _send_table(self, table: TableArray) -> None:
        """Internal method to send table."""
        if self._socket is None:
            raise RuntimeError("Not connected")
        self._socket.sendall(table.to_bytes())

    def _recv_exact(self, size: int) -> bytes:
        """Receive exact number of bytes.

        Args:
            size: Number of bytes to receive

        Returns:
            Received bytes

        Raises:
            ConnectionError: If connection is closed
        """
        if self._socket is None:
            raise RuntimeError("Not connected")

        data = bytearray()
        while len(data) < size:
            chunk = self._socket.recv(size - len(data))
            if not chunk:
                raise ConnectionError("Connection closed by server")
            data.extend(chunk)
        return bytes(data)

    def __enter__(self) -> "GameConnection":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()


# High-level functions matching C API

def start_game(conn: GameConnection) -> TableArray:
    """Receive initial hand cards at game start.

    Corresponds to C: startGame()

    Args:
        conn: Active connection

    Returns:
        TableArray containing initial hand
    """
    return conn.receive_table()


def send_changing_cards(conn: GameConnection, cards: TableArray) -> None:
    """Send cards for exchange phase.

    Corresponds to C: sendChangingCards()

    Args:
        conn: Active connection
        cards: Cards to exchange
    """
    conn.send_table(cards)


def receive_cards(conn: GameConnection) -> tuple[TableArray, bool]:
    """Receive card information during turn.

    Corresponds to C: receiveCards()

    Args:
        conn: Active connection

    Returns:
        Tuple of (TableArray, is_my_turn)
    """
    table = conn.receive_table()
    is_my_turn = table.get(5, 2) == 1
    return table, is_my_turn


def send_cards(conn: GameConnection, cards: TableArray) -> int:
    """Send selected cards and receive acceptance flag.

    Corresponds to C: sendCards()

    Args:
        conn: Active connection
        cards: Selected cards to play

    Returns:
        Acceptance flag (1 = accepted, 0 = rejected)
    """
    conn.send_table(cards)
    accept_flag = conn.receive_int()
    return accept_flag


def look_field(conn: GameConnection) -> TableArray:
    """Receive current field state after a play.

    Corresponds to C: lookField()

    Args:
        conn: Active connection

    Returns:
        TableArray with field cards
    """
    return conn.receive_table()


def be_game_end(conn: GameConnection) -> int:
    """Check if game has ended.

    Corresponds to C: beGameEnd()

    Args:
        conn: Active connection

    Returns:
        0: Game continues
        1: Current game ended
        2: All games ended
    """
    return conn.receive_int()
