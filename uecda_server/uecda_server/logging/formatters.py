"""Formatters for game log output."""

from uecda_server.models.card import Card, CardSet, Rank, Suit

# Suit codes for log output
SUIT_CODES: dict[Suit, str] = {
    Suit.SPADE: "S",
    Suit.HEART: "H",
    Suit.DIAMOND: "D",
    Suit.CLUB: "C",
}

# Rank codes for log output (reusing the same mapping as RANK_NAMES)
RANK_CODES: dict[Rank, str] = {
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


def format_card(card: Card) -> str:
    """Format a single card to string.

    Args:
        card: Card to format.

    Returns:
        Formatted string (e.g., "S3" for Spade 3, "Jo" for Joker).
    """
    if card.is_joker:
        return "Jo"
    if card.rank is None:
        raise ValueError("Non-joker card must have a rank")
    return f"{SUIT_CODES[card.suit]}{RANK_CODES[card.rank]}"


def format_cards(cards: CardSet) -> str:
    """Format a CardSet to comma-separated string.

    Args:
        cards: CardSet to format.

    Returns:
        Comma-separated card strings (e.g., "S8,H8,D8").
        Empty string if no cards.
    """
    if cards.is_empty():
        return ""
    return ",".join(format_card(c) for c in cards.to_list())


def format_hands(hands: list[CardSet]) -> dict[str, str]:
    """Format all players' hands to dict.

    Args:
        hands: List of CardSets indexed by player_id.

    Returns:
        Dict mapping player_id (as string) to formatted hand string.
    """
    return {str(i): format_cards(h) for i, h in enumerate(hands)}
