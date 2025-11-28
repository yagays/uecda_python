"""Card analysis for submitted plays."""

from dataclasses import dataclass
from enum import IntEnum

from uecda_server.models.card import Card, CardSet
from uecda_server.models.game_state import CardType


class AnalysisError(IntEnum):
    """Error codes from card analysis."""

    NONE = 0
    MULTIPLE_JOKERS = 1
    INVALID_POSITION = 2
    SEQUENCE_TOO_SHORT = 3
    INVALID_SUIT = 4
    COUNT_MISMATCH = 5


@dataclass
class CardAnalysis:
    """Result of analyzing submitted cards.

    Matches the C implementation's status_of_submitted_card[4]:
    - [0]: minimum value of cards (base_rank)
    - [1]: number of cards (count)
    - [2]: suit bit pattern (suit_pattern)
    - [3]: type (card_type)
    """

    base_rank: int  # Minimum rank value (1-13, or adjusted for revolution)
    count: int  # Number of cards
    suit_pattern: int  # Bit pattern: bit 0=Spade, 1=Heart, 2=Diamond, 3=Club
    card_type: CardType  # Type of play
    error: AnalysisError = AnalysisError.NONE
    has_joker_substitute: bool = False  # Joker used as substitute

    @property
    def is_valid(self) -> bool:
        """Check if analysis found no errors."""
        return self.error == AnalysisError.NONE

    @property
    def is_pass(self) -> bool:
        """Check if this is a pass (no cards)."""
        return self.card_type == CardType.EMPTY

    def matches_suit(self, other_pattern: int) -> bool:
        """Check if suit patterns match (for lock/shibari)."""
        return self.suit_pattern == other_pattern


class CardAnalyzer:
    """Analyzes submitted card combinations."""

    def analyze(
        self,
        cards: CardSet,
        joker_positions: dict[tuple[int, int], bool] | None = None,
        revolution: bool = False,
    ) -> CardAnalysis:
        """Analyze a submitted card combination.

        Args:
            cards: Cards to analyze
            joker_positions: Positions where joker is used as substitute
            revolution: Whether revolution is active

        Returns:
            CardAnalysis result
        """
        joker_positions = joker_positions or {}

        # Count cards and check for joker
        card_count = cards.count()
        has_joker = cards.has_joker() or bool(joker_positions)
        joker_count = 1 if has_joker else 0

        # Pass (no cards)
        if card_count == 0:
            return CardAnalysis(
                base_rank=-1,
                count=0,
                suit_pattern=0,
                card_type=CardType.EMPTY,
            )

        # Check for multiple jokers (error)
        if joker_count > 1:
            return CardAnalysis(
                base_rank=-1,
                count=card_count,
                suit_pattern=0,
                card_type=CardType.EMPTY,
                error=AnalysisError.MULTIPLE_JOKERS,
            )

        # Get non-joker cards
        normal_cards = [c for c in cards if not c.is_joker]

        # Single joker play
        if card_count == 1 and has_joker and not normal_cards:
            return CardAnalysis(
                base_rank=14,  # Joker is highest
                count=1,
                suit_pattern=0,
                card_type=CardType.JOKER_SINGLE,
            )

        # Single card
        if card_count == 1:
            card = normal_cards[0]
            return CardAnalysis(
                base_rank=card.rank,
                count=1,
                suit_pattern=1 << card.suit,
                card_type=CardType.SINGLE,
            )

        # Multiple cards - check for sequence (階段) or pair
        return self._analyze_multiple(
            normal_cards, joker_positions, has_joker, revolution
        )

    def _analyze_multiple(
        self,
        cards: list[Card],
        joker_positions: dict[tuple[int, int], bool],
        has_joker: bool,
        revolution: bool,
    ) -> CardAnalysis:
        """Analyze multiple card combination.

        Args:
            cards: List of non-joker cards
            joker_positions: Joker substitute positions
            has_joker: Whether joker is involved
            revolution: Whether revolution is active

        Returns:
            CardAnalysis result
        """
        if not cards and not joker_positions:
            return CardAnalysis(
                base_rank=-1,
                count=0,
                suit_pattern=0,
                card_type=CardType.EMPTY,
            )

        # Combine actual cards with joker substitutes
        all_positions: list[tuple[int, int]] = []
        for card in cards:
            all_positions.append((card.suit, card.rank))
        for pos in joker_positions:
            if pos not in all_positions:
                all_positions.append(pos)

        if not all_positions:
            return CardAnalysis(
                base_rank=-1,
                count=0,
                suit_pattern=0,
                card_type=CardType.EMPTY,
            )

        # Sort by rank
        all_positions.sort(key=lambda p: p[1])

        # Check if all same suit (potential sequence)
        suits = set(p[0] for p in all_positions)
        ranks = sorted(p[1] for p in all_positions)

        # Check for sequence (階段): same suit, consecutive ranks
        if len(suits) == 1:
            is_sequence = True
            for i in range(1, len(ranks)):
                if ranks[i] != ranks[i - 1] + 1:
                    is_sequence = False
                    break

            if is_sequence:
                card_count = len(all_positions)
                if card_count < 3:
                    return CardAnalysis(
                        base_rank=ranks[0],
                        count=card_count,
                        suit_pattern=1 << list(suits)[0],
                        card_type=CardType.SEQUENCE,
                        error=AnalysisError.SEQUENCE_TOO_SHORT,
                    )

                # For revolution, base_rank is the highest rank
                base_rank = ranks[-1] if revolution else ranks[0]

                return CardAnalysis(
                    base_rank=base_rank,
                    count=card_count,
                    suit_pattern=1 << list(suits)[0],
                    card_type=CardType.SEQUENCE,
                    has_joker_substitute=has_joker,
                )

        # Check for pair (same rank, different suits)
        if len(set(ranks)) == 1:
            # All same rank = pair
            suit_pattern = 0
            for suit, _ in all_positions:
                suit_pattern |= 1 << suit

            # Check for invalid suit (joker row used incorrectly)
            if suit_pattern >= 16 and suit_pattern != 31:
                return CardAnalysis(
                    base_rank=ranks[0],
                    count=len(all_positions),
                    suit_pattern=suit_pattern,
                    card_type=CardType.PAIR,
                    error=AnalysisError.INVALID_SUIT,
                )

            return CardAnalysis(
                base_rank=ranks[0],
                count=len(all_positions),
                suit_pattern=suit_pattern,
                card_type=CardType.PAIR,
                has_joker_substitute=has_joker,
            )

        # Invalid combination
        return CardAnalysis(
            base_rank=-1,
            count=len(all_positions),
            suit_pattern=0,
            card_type=CardType.EMPTY,
            error=AnalysisError.COUNT_MISMATCH,
        )

    def check_special_card(
        self,
        analysis: CardAnalysis,
        special_rank: int,
        revolution: bool = False,
    ) -> bool:
        """Check if the played cards include a special rank (e.g., 8 for 8-giri).

        Args:
            analysis: Card analysis result
            special_rank: Rank to check for (1-13, where 1=3, 6=8, etc.)
            revolution: Whether revolution is active

        Returns:
            True if special card is included
        """
        if analysis.card_type == CardType.SEQUENCE:
            # For sequence, check if special_rank is within range
            if revolution:
                # In revolution, base_rank is highest
                low = analysis.base_rank - analysis.count + 1
                high = analysis.base_rank
            else:
                # Normal: base_rank is lowest
                low = analysis.base_rank
                high = analysis.base_rank + analysis.count - 1
            return low <= special_rank <= high
        else:
            # For single/pair, just compare base_rank
            return analysis.base_rank == special_rank
