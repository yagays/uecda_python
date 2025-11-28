"""Card and CardSet models."""

from enum import IntEnum
from typing import Iterator

from pydantic import BaseModel


class Suit(IntEnum):
    """Card suit (matches protocol array row indices)."""

    SPADE = 0
    HEART = 1
    DIAMOND = 2
    CLUB = 3
    JOKER = 4


class Rank(IntEnum):
    """Card rank (matches protocol array column indices 1-13).

    Value represents the column index in the 8x15 table.
    Strength order (normal): 3 < 4 < ... < K < A < 2
    """

    THREE = 1
    FOUR = 2
    FIVE = 3
    SIX = 4
    SEVEN = 5
    EIGHT = 6
    NINE = 7
    TEN = 8
    JACK = 9
    QUEEN = 10
    KING = 11
    ACE = 12
    TWO = 13


# Map rank to display string
RANK_NAMES = {
    Rank.THREE: "3",
    Rank.FOUR: "4",
    Rank.FIVE: "5",
    Rank.SIX: "6",
    Rank.SEVEN: "7",
    Rank.EIGHT: "8",
    Rank.NINE: "9",
    Rank.TEN: "10",
    Rank.JACK: "J",
    Rank.QUEEN: "Q",
    Rank.KING: "K",
    Rank.ACE: "A",
    Rank.TWO: "2",
}

SUIT_SYMBOLS = {
    Suit.SPADE: "♠",
    Suit.HEART: "♥",
    Suit.DIAMOND: "♦",
    Suit.CLUB: "♣",
    Suit.JOKER: "🃏",
}


class Card(BaseModel, frozen=True):
    """Single card representation."""

    suit: Suit
    rank: Rank | None = None  # None for Joker

    @property
    def is_joker(self) -> bool:
        """Check if this card is a joker."""
        return self.suit == Suit.JOKER

    def strength(self, revolution: bool = False) -> int:
        """Get card strength for comparison.

        Args:
            revolution: If True, reverse the strength order (except Joker).

        Returns:
            Strength value. Higher is stronger.
        """
        if self.is_joker:
            return 100  # Always strongest
        if self.rank is None:
            raise ValueError("Non-joker card must have a rank")

        if revolution:
            # In revolution: 2 is weakest, 3 is strongest
            return 14 - self.rank
        return self.rank

    def __str__(self) -> str:
        if self.is_joker:
            return "Joker"
        return f"{SUIT_SYMBOLS[self.suit]}{RANK_NAMES[self.rank]}"

    def __repr__(self) -> str:
        return str(self)


class CardSet:
    """Set of cards with protocol table conversion support.

    The protocol uses an 8x15 integer array where:
    - Rows 0-3: Spade, Heart, Diamond, Club
    - Row 4: Joker (column 1, value 2 means joker present)
    - Columns 1-13: Card ranks (3, 4, 5, ..., K, A, 2)
    - Value 0: Card not present
    - Value 1: Normal card present
    - Value 2: Joker used as this card
    """

    def __init__(self, cards: set[Card] | None = None):
        """Initialize card set.

        Args:
            cards: Initial set of cards.
        """
        self._cards: set[Card] = cards.copy() if cards else set()

    def add(self, card: Card) -> None:
        """Add a card to the set."""
        self._cards.add(card)

    def remove(self, card: Card) -> None:
        """Remove a card from the set."""
        self._cards.discard(card)

    def contains(self, card: Card) -> bool:
        """Check if card is in the set."""
        return card in self._cards

    def clear(self) -> None:
        """Remove all cards."""
        self._cards.clear()

    def count(self) -> int:
        """Get number of cards."""
        return len(self._cards)

    def is_empty(self) -> bool:
        """Check if set is empty."""
        return len(self._cards) == 0

    def has_joker(self) -> bool:
        """Check if joker is in the set."""
        return any(c.is_joker for c in self._cards)

    def get_joker(self) -> Card | None:
        """Get the joker card if present."""
        for c in self._cards:
            if c.is_joker:
                return c
        return None

    def cards_by_rank(self, rank: Rank) -> list[Card]:
        """Get all cards with the specified rank."""
        return [c for c in self._cards if c.rank == rank and not c.is_joker]

    def cards_by_suit(self, suit: Suit) -> list[Card]:
        """Get all cards with the specified suit."""
        return [c for c in self._cards if c.suit == suit]

    def to_list(self) -> list[Card]:
        """Get cards as a sorted list."""
        return sorted(
            self._cards,
            key=lambda c: (c.suit, c.rank if c.rank else 0),
        )

    def copy(self) -> "CardSet":
        """Create a copy of this card set."""
        return CardSet(self._cards)

    def __iter__(self) -> Iterator[Card]:
        return iter(self._cards)

    def __len__(self) -> int:
        return len(self._cards)

    def __contains__(self, card: Card) -> bool:
        return card in self._cards

    def __sub__(self, other: "CardSet") -> "CardSet":
        """Set difference."""
        return CardSet(self._cards - other._cards)

    def __or__(self, other: "CardSet") -> "CardSet":
        """Set union."""
        return CardSet(self._cards | other._cards)

    def __and__(self, other: "CardSet") -> "CardSet":
        """Set intersection."""
        return CardSet(self._cards & other._cards)

    def __str__(self) -> str:
        if not self._cards:
            return "[]"
        return "[" + ", ".join(str(c) for c in self.to_list()) + "]"

    def __repr__(self) -> str:
        return f"CardSet({self._cards!r})"


def create_full_deck() -> CardSet:
    """Create a full 53-card deck (52 + 1 joker)."""
    cards = CardSet()

    # Add all suit cards
    for suit in [Suit.SPADE, Suit.HEART, Suit.DIAMOND, Suit.CLUB]:
        for rank in Rank:
            cards.add(Card(suit=suit, rank=rank))

    # Add joker
    cards.add(Card(suit=Suit.JOKER, rank=None))

    return cards
