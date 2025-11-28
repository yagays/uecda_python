"""Game state models."""

from enum import Enum

from pydantic import BaseModel, Field

from .card import CardSet


class CardType(str, Enum):
    """Type of card combination played."""

    EMPTY = "empty"  # No cards on field
    SINGLE = "single"  # Single card
    PAIR = "pair"  # Multiple cards of same rank
    SEQUENCE = "sequence"  # Consecutive cards of same suit (階段)
    JOKER_SINGLE = "joker_single"  # Joker played alone


class FieldState(BaseModel):
    """State of the playing field."""

    cards: CardSet = Field(default_factory=CardSet)
    card_type: CardType = CardType.EMPTY
    card_count: int = 0
    base_rank: int = -1  # Base rank for comparison
    suit_pattern: int = 0  # Bit pattern of suits (for lock)

    is_locked: bool = False  # 縛り active
    lock_count: int = 0  # Number of consecutive same-suit plays

    model_config = {"arbitrary_types_allowed": True}

    def clear(self) -> None:
        """Clear the field (場が流れる)."""
        self.cards = CardSet()
        self.card_type = CardType.EMPTY
        self.card_count = 0
        self.base_rank = -1
        self.suit_pattern = 0
        self.is_locked = False
        self.lock_count = 0

    def is_empty(self) -> bool:
        """Check if field is empty."""
        return self.card_type == CardType.EMPTY

    def __str__(self) -> str:
        if self.is_empty():
            return "Field: [empty]"
        lock_str = " [LOCK]" if self.is_locked else ""
        return f"Field: {self.cards}{lock_str}"


class GameState(BaseModel):
    """Overall game state."""

    # Game progress
    game_number: int = 1
    turn_number: int = 0

    # Current turn info
    current_player: int = 0  # Player ID whose turn it is
    last_player: int = -1  # Last player who played cards (not passed)
    direction: int = 1  # 1 = clockwise, -1 = counter-clockwise

    # Special states
    is_revolution: bool = False  # 革命
    is_eleven_back: bool = False  # 11バック (temporary revolution)
    is_joker_single: bool = False  # Joker played alone (can be beaten by spade 3)

    # Pass tracking
    consecutive_passes: int = 0
    finished_count: int = 0  # Number of players who finished

    # Field
    field: FieldState = Field(default_factory=FieldState)

    def effective_revolution(self) -> bool:
        """Get effective revolution state (considering 11-back)."""
        # 11-back XORs with revolution
        return self.is_revolution != self.is_eleven_back

    def reset_for_new_round(self) -> None:
        """Reset state when field is cleared (場が流れる)."""
        self.field.clear()
        self.consecutive_passes = 0
        self.is_joker_single = False
        self.is_eleven_back = False  # 11-back ends when field clears

    def reset_for_new_game(self) -> None:
        """Reset state for a new game."""
        self.turn_number = 0
        self.current_player = 0
        self.last_player = -1
        self.direction = 1
        self.is_revolution = False
        self.is_eleven_back = False
        self.is_joker_single = False
        self.consecutive_passes = 0
        self.finished_count = 0
        self.field.clear()

    def __str__(self) -> str:
        parts = [f"Game {self.game_number}, Turn {self.turn_number}"]
        if self.is_revolution:
            parts.append("[REVOLUTION]")
        if self.is_eleven_back:
            parts.append("[11-BACK]")
        parts.append(f"Player {self.current_player}'s turn")
        return " ".join(parts)
