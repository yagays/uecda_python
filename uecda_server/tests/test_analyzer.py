"""Tests for card analyzer."""

import pytest

from uecda_server.game.analyzer import CardAnalyzer, AnalysisError
from uecda_server.models.card import Card, CardSet, Rank, Suit
from uecda_server.models.game_state import CardType


@pytest.fixture
def analyzer():
    return CardAnalyzer()


class TestCardAnalyzer:
    """Tests for CardAnalyzer class."""

    def test_analyze_empty(self, analyzer):
        """Test analyzing empty card set (pass)."""
        cards = CardSet()
        result = analyzer.analyze(cards)

        assert result.is_pass
        assert result.card_type == CardType.EMPTY
        assert result.count == 0

    def test_analyze_single(self, analyzer):
        """Test analyzing single card."""
        cards = CardSet()
        cards.add(Card(suit=Suit.SPADE, rank=Rank.ACE))

        result = analyzer.analyze(cards)

        assert result.card_type == CardType.SINGLE
        assert result.count == 1
        assert result.base_rank == Rank.ACE
        assert result.suit_pattern == 1  # Spade = bit 0

    def test_analyze_joker_single(self, analyzer):
        """Test analyzing single joker."""
        cards = CardSet()
        cards.add(Card(suit=Suit.JOKER))

        result = analyzer.analyze(cards)

        assert result.card_type == CardType.JOKER_SINGLE
        assert result.count == 1
        assert result.base_rank == 14  # Joker is highest

    def test_analyze_pair(self, analyzer):
        """Test analyzing pair."""
        cards = CardSet()
        cards.add(Card(suit=Suit.SPADE, rank=Rank.FIVE))
        cards.add(Card(suit=Suit.HEART, rank=Rank.FIVE))

        result = analyzer.analyze(cards)

        assert result.card_type == CardType.PAIR
        assert result.count == 2
        assert result.base_rank == Rank.FIVE
        assert result.suit_pattern == 0b0011  # Spade + Heart

    def test_analyze_triple(self, analyzer):
        """Test analyzing triple (3 of a kind)."""
        cards = CardSet()
        cards.add(Card(suit=Suit.SPADE, rank=Rank.SEVEN))
        cards.add(Card(suit=Suit.HEART, rank=Rank.SEVEN))
        cards.add(Card(suit=Suit.DIAMOND, rank=Rank.SEVEN))

        result = analyzer.analyze(cards)

        assert result.card_type == CardType.PAIR
        assert result.count == 3
        assert result.base_rank == Rank.SEVEN

    def test_analyze_sequence(self, analyzer):
        """Test analyzing sequence (階段)."""
        cards = CardSet()
        cards.add(Card(suit=Suit.SPADE, rank=Rank.FIVE))
        cards.add(Card(suit=Suit.SPADE, rank=Rank.SIX))
        cards.add(Card(suit=Suit.SPADE, rank=Rank.SEVEN))

        result = analyzer.analyze(cards)

        assert result.card_type == CardType.SEQUENCE
        assert result.count == 3
        assert result.base_rank == Rank.FIVE  # Lowest card

    def test_analyze_sequence_revolution(self, analyzer):
        """Test analyzing sequence in revolution mode."""
        cards = CardSet()
        cards.add(Card(suit=Suit.HEART, rank=Rank.NINE))
        cards.add(Card(suit=Suit.HEART, rank=Rank.TEN))
        cards.add(Card(suit=Suit.HEART, rank=Rank.JACK))

        result = analyzer.analyze(cards, revolution=True)

        assert result.card_type == CardType.SEQUENCE
        assert result.count == 3
        assert result.base_rank == Rank.JACK  # Highest card in revolution

    def test_analyze_sequence_too_short(self, analyzer):
        """Test that 2-card sequence is invalid."""
        cards = CardSet()
        cards.add(Card(suit=Suit.SPADE, rank=Rank.FIVE))
        cards.add(Card(suit=Suit.SPADE, rank=Rank.SIX))

        result = analyzer.analyze(cards)

        # Should be recognized as sequence but with error
        assert result.error == AnalysisError.SEQUENCE_TOO_SHORT

    def test_check_special_card_single(self, analyzer):
        """Test checking for special card in single."""
        cards = CardSet()
        cards.add(Card(suit=Suit.SPADE, rank=Rank.EIGHT))

        result = analyzer.analyze(cards)

        # Check for 8 (8切り)
        assert analyzer.check_special_card(result, Rank.EIGHT, revolution=False)
        assert not analyzer.check_special_card(result, Rank.FIVE, revolution=False)

    def test_check_special_card_sequence(self, analyzer):
        """Test checking for special card in sequence."""
        cards = CardSet()
        cards.add(Card(suit=Suit.CLUB, rank=Rank.SEVEN))
        cards.add(Card(suit=Suit.CLUB, rank=Rank.EIGHT))
        cards.add(Card(suit=Suit.CLUB, rank=Rank.NINE))

        result = analyzer.analyze(cards)

        # 8 is within the sequence 7-8-9
        assert analyzer.check_special_card(result, Rank.EIGHT, revolution=False)
        assert analyzer.check_special_card(result, Rank.SEVEN, revolution=False)
        assert analyzer.check_special_card(result, Rank.NINE, revolution=False)
        assert not analyzer.check_special_card(result, Rank.TEN, revolution=False)


class TestRevolution:
    """Tests for revolution-related analysis."""

    def test_pair_revolution(self, analyzer):
        """Test 4-card pair triggers revolution."""
        cards = CardSet()
        for suit in [Suit.SPADE, Suit.HEART, Suit.DIAMOND, Suit.CLUB]:
            cards.add(Card(suit=suit, rank=Rank.FIVE))

        result = analyzer.analyze(cards)

        assert result.card_type == CardType.PAIR
        assert result.count == 4
        # Revolution detection is done by the engine, not analyzer

    def test_sequence_revolution(self, analyzer):
        """Test 5-card sequence triggers revolution."""
        cards = CardSet()
        for rank in [Rank.THREE, Rank.FOUR, Rank.FIVE, Rank.SIX, Rank.SEVEN]:
            cards.add(Card(suit=Suit.SPADE, rank=rank))

        result = analyzer.analyze(cards)

        assert result.card_type == CardType.SEQUENCE
        assert result.count == 5
