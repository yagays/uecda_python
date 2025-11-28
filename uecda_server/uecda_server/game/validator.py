"""Move validation for submitted plays."""

from dataclasses import dataclass

from uecda_server.models.card import CardSet, Rank, Suit
from uecda_server.models.game_state import CardType, GameState

from .analyzer import CardAnalysis, CardAnalyzer


@dataclass
class ValidationResult:
    """Result of move validation."""

    is_valid: bool
    error_message: str = ""
    is_pass: bool = False


class MoveValidator:
    """Validates submitted card plays."""

    def __init__(self, analyzer: CardAnalyzer | None = None):
        """Initialize validator.

        Args:
            analyzer: CardAnalyzer instance (creates one if not provided)
        """
        self.analyzer = analyzer or CardAnalyzer()

    def validate(
        self,
        submitted: CardAnalysis,
        player_hand: CardSet,
        submitted_cards: CardSet,
        game_state: GameState,
        joker_positions: dict[tuple[int, int], bool] | None = None,
    ) -> ValidationResult:
        """Validate a submitted play.

        Args:
            submitted: Analysis of submitted cards
            player_hand: Player's current hand
            submitted_cards: The actual cards being submitted
            game_state: Current game state
            joker_positions: Positions where joker is used as substitute

        Returns:
            ValidationResult
        """
        joker_positions = joker_positions or {}
        field = game_state.field

        # Check for pass
        if submitted.is_pass:
            return ValidationResult(is_valid=True, is_pass=True)

        # Check for analysis errors
        if not submitted.is_valid:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid card combination: {submitted.error.name}",
            )

        # Check that player has the submitted cards
        if not self._check_hand_contains(player_hand, submitted_cards, joker_positions):
            return ValidationResult(
                is_valid=False,
                error_message="Player does not have the submitted cards",
            )

        # If field is empty, any valid combination is allowed
        if field.is_empty():
            return ValidationResult(is_valid=True)

        # Compare with field
        return self._compare_with_field(submitted, game_state)

    def _check_hand_contains(
        self,
        hand: CardSet,
        submitted: CardSet,
        joker_positions: dict[tuple[int, int], bool],
    ) -> bool:
        """Check if hand contains all submitted cards.

        Args:
            hand: Player's hand
            submitted: Cards being submitted
            joker_positions: Joker substitute positions

        Returns:
            True if hand contains all cards
        """
        # Check for joker usage
        joker_used = bool(joker_positions)
        if joker_used and not hand.has_joker():
            return False

        # Check each non-joker card
        for card in submitted:
            if card.is_joker:
                continue
            # Skip cards that are joker substitutes
            if (card.suit, card.rank) in joker_positions:
                continue
            if card not in hand:
                return False

        return True

    def _compare_with_field(
        self,
        submitted: CardAnalysis,
        game_state: GameState,
    ) -> ValidationResult:
        """Compare submitted cards with field.

        Args:
            submitted: Analysis of submitted cards
            game_state: Current game state

        Returns:
            ValidationResult
        """
        field = game_state.field
        revolution = game_state.effective_revolution()

        # Special case: Joker single can be played on any single card
        if submitted.card_type == CardType.JOKER_SINGLE:
            if field.card_type == CardType.SINGLE:
                return ValidationResult(is_valid=True)
            return ValidationResult(
                is_valid=False,
                error_message="Joker single can only be played on single cards",
            )

        # Special case: Spade 3 can beat joker single
        if game_state.is_joker_single:
            if (
                submitted.card_type == CardType.SINGLE
                and submitted.base_rank == Rank.THREE
                and submitted.suit_pattern == (1 << Suit.SPADE)
            ):
                return ValidationResult(is_valid=True)

        # Card count must match
        if submitted.count != field.card_count:
            return ValidationResult(
                is_valid=False,
                error_message=f"Card count mismatch: {submitted.count} vs {field.card_count}",
            )

        # Card type must match (except joker single -> single)
        if submitted.card_type != field.card_type:
            return ValidationResult(
                is_valid=False,
                error_message=f"Card type mismatch: {submitted.card_type} vs {field.card_type}",
            )

        # Check lock (shibari)
        if field.is_locked and submitted.suit_pattern != field.suit_pattern:
            return ValidationResult(
                is_valid=False,
                error_message="Lock active: must play same suit",
            )

        # Compare rank based on card type
        if submitted.card_type == CardType.PAIR:
            # For pairs, compare base rank directly
            if revolution:
                # In revolution, lower is stronger
                if submitted.base_rank >= field.base_rank:
                    return ValidationResult(
                        is_valid=False,
                        error_message="Submitted pair is not stronger (revolution)",
                    )
            else:
                # Normal: higher is stronger
                if submitted.base_rank <= field.base_rank:
                    return ValidationResult(
                        is_valid=False,
                        error_message="Submitted pair is not stronger",
                    )
        else:
            # For single/sequence
            if revolution:
                # In revolution, must have lower highest card
                submitted_highest = submitted.base_rank
                field_highest = field.base_rank
                if submitted.card_type == CardType.SEQUENCE and not revolution:
                    submitted_highest = submitted.base_rank + submitted.count - 1
                    field_highest = field.base_rank + field.card_count - 1

                if submitted_highest >= field_highest:
                    return ValidationResult(
                        is_valid=False,
                        error_message="Submitted cards not stronger (revolution)",
                    )
            else:
                # Normal: must have higher lowest card
                # For sequences, we need to beat the lowest card of field sequence
                if submitted.base_rank <= field.base_rank:
                    return ValidationResult(
                        is_valid=False,
                        error_message="Submitted cards not stronger",
                    )

        return ValidationResult(is_valid=True)

    def validate_exchange(
        self,
        cards: CardSet,
        expected_count: int,
        hand: CardSet,
        must_give_strongest: bool = False,
    ) -> ValidationResult:
        """Validate card exchange selection.

        Args:
            cards: Cards selected for exchange
            expected_count: Expected number of cards
            hand: Player's hand
            must_give_strongest: If True, must give strongest cards (大貧民/貧民)

        Returns:
            ValidationResult
        """
        if cards.count() != expected_count:
            return ValidationResult(
                is_valid=False,
                error_message=f"Must exchange exactly {expected_count} cards",
            )

        # Check all cards are in hand
        for card in cards:
            if card not in hand:
                return ValidationResult(
                    is_valid=False,
                    error_message="Selected card not in hand",
                )

        # For 大貧民/貧民, must give strongest cards
        if must_give_strongest:
            # Get hand sorted by strength (descending)
            hand_sorted = sorted(
                hand.to_list(),
                key=lambda c: c.strength(),
                reverse=True,
            )
            strongest = set(hand_sorted[:expected_count])
            selected = set(cards)

            if selected != strongest:
                return ValidationResult(
                    is_valid=False,
                    error_message="Must give strongest cards",
                )

        return ValidationResult(is_valid=True)
