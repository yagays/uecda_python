"""Protocol definitions and table array handling.

The UECda protocol uses an 8x15 integer array for communication.
Data is transmitted in network byte order (big-endian).

Table format:
- Rows 0-3: Card suits (Spade, Heart, Diamond, Club)
- Row 4: Joker (column 1, value 2 = joker present)
- Row 5: Game state info
- Row 6: Player info
- Row 7: Reserved

Column indices for cards (rows 0-4):
- Column 0: Unused
- Columns 1-13: Card ranks (3, 4, 5, 6, 7, 8, 9, 10, J, Q, K, A, 2)
- Column 14: Unused

Row 5 (game state):
- [5][0]: Exchange phase flag (0=exchange needed, 1=initial hand)
- [5][1]: Cards to exchange (2 for daifugo, 1 for fugo, 0 otherwise)
- [5][2]: Is my turn (1 = yes, 0 = no)
- [5][3]: Current player number
- [5][4]: Field is empty (onset)
- [5][5]: 11-back active
- [5][6]: Revolution active
- [5][7]: Lock (shibari) active

Row 6 (player info):
- [6][0-4]: Hand count for players 0-4
- [6][5-9]: Rank for players 0-4
- [6][10-14]: Seat position for seats 0-4

Card values:
- 0: No card
- 1: Normal card present
- 2: Joker (or joker used as substitute)
"""

import struct

from uecda_client.models.card import Card, CardSet, Rank, Suit

# Protocol version
PROTOCOL_VERSION = 20070

# Table dimensions
TABLE_ROWS = 8
TABLE_COLS = 15
TABLE_SIZE = TABLE_ROWS * TABLE_COLS  # 120 integers
TABLE_BYTES = TABLE_SIZE * 4  # 480 bytes


class TableArray:
    """8x15 integer array for protocol communication."""

    def __init__(self):
        """Initialize with zeros."""
        self.data: list[list[int]] = [[0] * TABLE_COLS for _ in range(TABLE_ROWS)]

    def clear(self) -> None:
        """Reset all values to zero."""
        for i in range(TABLE_ROWS):
            for j in range(TABLE_COLS):
                self.data[i][j] = 0

    def get(self, row: int, col: int) -> int:
        """Get value at position."""
        return self.data[row][col]

    def set(self, row: int, col: int, value: int) -> None:
        """Set value at position."""
        self.data[row][col] = value

    def set_cards(self, cards: CardSet) -> None:
        """Set card information in rows 0-4.

        Args:
            cards: CardSet to encode
        """
        # Clear card rows
        for i in range(5):
            for j in range(TABLE_COLS):
                self.data[i][j] = 0

        for card in cards:
            if card.is_joker:
                # Joker is at [4][1] with value 2
                self.data[Suit.JOKER][1] = 2
            else:
                # Normal card at [suit][rank]
                self.data[card.suit][card.rank] = 1

    def get_cards(self) -> CardSet:
        """Extract cards from rows 0-4.

        Returns:
            CardSet containing the cards
        """
        cards = CardSet()

        # Check normal cards (rows 0-3)
        for suit in [Suit.SPADE, Suit.HEART, Suit.DIAMOND, Suit.CLUB]:
            for rank in Rank:
                if self.data[suit][rank] >= 1:
                    cards.add(Card(suit=suit, rank=rank))

        # Check joker (row 4, column 1)
        if self.data[Suit.JOKER][1] == 2:
            cards.add(Card(suit=Suit.JOKER))

        return cards

    def get_submitted_cards(self) -> tuple[CardSet, dict[tuple[int, int], bool]]:
        """Extract submitted cards, identifying joker substitutions.

        Returns:
            Tuple of (CardSet, dict of positions where joker is used as substitute)
        """
        cards = CardSet()
        joker_positions: dict[tuple[int, int], bool] = {}

        # Check all positions
        for suit in [Suit.SPADE, Suit.HEART, Suit.DIAMOND, Suit.CLUB]:
            for rank in Rank:
                val = self.data[suit][rank]
                if val == 1:
                    cards.add(Card(suit=suit, rank=rank))
                elif val == 2:
                    # Joker used as this card
                    joker_positions[(suit, rank)] = True
                    cards.add(Card(suit=suit, rank=rank))

        # Check for standalone joker (value 2 anywhere with no rank meaning)
        if not joker_positions:
            for suit in [Suit.SPADE, Suit.HEART, Suit.DIAMOND, Suit.CLUB]:
                for col in range(TABLE_COLS):
                    if self.data[suit][col] == 2:
                        cards.add(Card(suit=Suit.JOKER))
                        break
                if cards.has_joker():
                    break

        return cards, joker_positions

    def to_bytes(self) -> bytes:
        """Serialize to network byte order.

        Returns:
            480 bytes (8x15x4)
        """
        result = bytearray(TABLE_BYTES)
        for i in range(TABLE_ROWS):
            for j in range(TABLE_COLS):
                offset = (i * TABLE_COLS + j) * 4
                # Use unsigned int, treat negative as 0 (like C implementation)
                value = self.data[i][j] if self.data[i][j] >= 0 else 0
                struct.pack_into("!I", result, offset, value)
        return bytes(result)

    @classmethod
    def from_bytes(cls, data: bytes) -> "TableArray":
        """Deserialize from network byte order.

        Args:
            data: 480 bytes

        Returns:
            TableArray instance
        """
        if len(data) != TABLE_BYTES:
            raise ValueError(f"Expected {TABLE_BYTES} bytes, got {len(data)}")

        table = cls()
        for i in range(TABLE_ROWS):
            for j in range(TABLE_COLS):
                offset = (i * TABLE_COLS + j) * 4
                table.data[i][j] = struct.unpack_from("!I", data, offset)[0]
        return table

    def __str__(self) -> str:
        """String representation for debugging."""
        lines = []
        suit_names = ["S", "H", "D", "C", "J", "5", "6", "7"]
        for i in range(TABLE_ROWS):
            row_str = f"{suit_names[i]}: " + " ".join(
                f"{self.data[i][j]:2d}" for j in range(TABLE_COLS)
            )
            lines.append(row_str)
        return "\n".join(lines)


def create_profile_table(protocol_version: int, name: str) -> TableArray:
    """Create profile table for initial handshake.

    Args:
        protocol_version: Protocol version (e.g., 20070)
        name: Player name (max 14 characters)

    Returns:
        TableArray with profile info
    """
    table = TableArray()
    table.data[0][0] = protocol_version

    # Name in row 1, one character per column
    name_bytes = name.encode("ascii", errors="replace")[:14]
    for i, byte in enumerate(name_bytes):
        table.data[1][i] = byte
    # Null terminate
    if len(name_bytes) < 15:
        table.data[1][len(name_bytes)] = 0

    return table


def int_to_bytes(value: int) -> bytes:
    """Serialize integer to network byte order.

    Args:
        value: Integer value

    Returns:
        4 bytes
    """
    value = value if value >= 0 else 0
    return struct.pack("!I", value)


def bytes_to_int(data: bytes) -> int:
    """Deserialize integer from network byte order.

    Args:
        data: 4 bytes

    Returns:
        Integer value
    """
    return struct.unpack("!I", data)[0]
