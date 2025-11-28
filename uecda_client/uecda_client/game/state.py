"""Game state parsing from table arrays.

Corresponds to C implementation: daihinmin.c getState(), getField()
"""

from dataclasses import dataclass, field

from uecda_client.models.card import CardSet
from uecda_client.network.protocol import TableArray


@dataclass
class GameState:
    """Current game state parsed from server table.

    Corresponds to C: struct state_type

    Fields match the C implementation:
    - ord: Current card rank on field (0-14)
    - sequence: 1 if sequence (kaidan), 0 if group
    - qty: Number of cards on field
    - rev: 1 if revolution active, 0 otherwise
    - b11: 1 if 11-back active, 0 otherwise (unused in standard)
    - lock: 1 if lock (shibari) active, 0 otherwise
    - onset: 1 if field is empty (can lead), 0 otherwise
    - suit: List of suits currently on field (suit[i]=1 means suit i is present)
    - joker: 1 if I have joker, 0 otherwise
    - player_qty: Hand count for each player
    - player_rank: Rank (daifugo=0 to daihinmin=4) for each player
    - seat: Seat positions
    """

    # Field state
    ord: int = 0  # Current rank on field
    sequence: bool = False  # Is sequence (kaidan)
    qty: int = 0  # Number of cards
    rev: bool = False  # Revolution active
    b11: bool = False  # 11-back (unused)
    lock: bool = False  # Lock (shibari) active
    onset: bool = True  # Field is empty
    suit: list[int] = field(default_factory=lambda: [0, 0, 0, 0, 0])
    joker: bool = False  # Do I have joker

    # Player info
    player_qty: list[int] = field(default_factory=lambda: [0, 0, 0, 0, 0])
    player_rank: list[int] = field(default_factory=lambda: [0, 0, 0, 0, 0])
    seat: list[int] = field(default_factory=lambda: [0, 0, 0, 0, 0])

    @classmethod
    def from_table(cls, table: TableArray, my_cards: TableArray) -> "GameState":
        """Parse state from received table.

        Corresponds to C: getState()

        Args:
            table: Table received from server (own_cards_buf)
            my_cards: My current hand table

        Returns:
            Parsed GameState
        """
        state = cls()

        # Row 5: Game state flags
        # [5][4]: onset (field empty)
        state.onset = table.get(5, 4) == 1

        # [5][5]: 11-back
        state.b11 = table.get(5, 5) == 1

        # [5][6]: Revolution
        state.rev = table.get(5, 6) == 1

        # [5][7]: Lock (shibari)
        state.lock = table.get(5, 7) == 1

        # Row 6: Player info
        for i in range(5):
            state.player_qty[i] = table.get(6, i)  # [6][0-4]: hand counts
            state.player_rank[i] = table.get(6, 5 + i)  # [6][5-9]: ranks
            state.seat[i] = table.get(6, 10 + i)  # [6][10-14]: seats

        # Check if I have joker (row 4, col 1 in my_cards)
        state.joker = my_cards.get(4, 1) == 2

        # Parse field cards from row 7
        state._parse_field(table)

        return state

    def _parse_field(self, table: TableArray) -> None:
        """Parse field cards to determine ord, qty, sequence, suit.

        Corresponds to C: getField() partially
        """
        # Count cards and find ranks on field (row 7)
        card_count = 0
        ranks_found: list[int] = []
        suits_found: list[int] = []

        for suit in range(4):  # Spade, Heart, Diamond, Club
            for rank in range(1, 14):  # 3 to 2
                if table.get(suit, rank) >= 1:
                    card_count += 1
                    if rank not in ranks_found:
                        ranks_found.append(rank)
                    if suit not in suits_found:
                        suits_found.append(suit)
                    self.suit[suit] = 1

        # Check for joker on field (row 4 col 1, or value 2 anywhere)
        if table.get(4, 1) == 2:
            card_count += 1

        self.qty = card_count

        if card_count == 0:
            self.onset = True
            self.ord = 0
            return

        ranks_found.sort()

        # Determine if sequence or group
        if len(ranks_found) >= 2:
            # Check if consecutive (sequence)
            is_consecutive = True
            for i in range(1, len(ranks_found)):
                if ranks_found[i] - ranks_found[i - 1] != 1:
                    is_consecutive = False
                    break

            if is_consecutive and card_count == len(ranks_found):
                self.sequence = True
                self.ord = ranks_found[-1]  # Highest rank in sequence
            else:
                self.sequence = False
                self.ord = ranks_found[0]  # Rank of group
        elif len(ranks_found) == 1:
            self.sequence = False
            self.ord = ranks_found[0]
        else:
            # Only joker played alone
            self.sequence = False
            self.ord = 14  # Joker is highest


def get_field_cards(table: TableArray) -> CardSet:
    """Extract field cards from table (typically from row 7 data or rows 0-4).

    Args:
        table: Table from server (field info)

    Returns:
        CardSet of cards on field
    """
    return table.get_cards()


def analyze_field(table: TableArray) -> tuple[int, int, bool, list[int]]:
    """Analyze field cards from table.

    Returns:
        Tuple of (rank, qty, is_sequence, suits)
    """
    state = GameState()
    state._parse_field(table)
    return state.ord, state.qty, state.sequence, state.suit
