"""Tests for card models."""

import pytest

from uecda_server.models.card import (
    Card,
    CardSet,
    Rank,
    Suit,
    create_full_deck,
)


class TestCard:
    """Tests for Card class."""

    def test_create_normal_card(self):
        """Test creating a normal card."""
        card = Card(suit=Suit.SPADE, rank=Rank.ACE)
        assert card.suit == Suit.SPADE
        assert card.rank == Rank.ACE
        assert not card.is_joker

    def test_create_joker(self):
        """Test creating a joker."""
        joker = Card(suit=Suit.JOKER, rank=None)
        assert joker.suit == Suit.JOKER
        assert joker.rank is None
        assert joker.is_joker

    def test_strength_normal(self):
        """Test card strength in normal order."""
        three = Card(suit=Suit.SPADE, rank=Rank.THREE)
        two = Card(suit=Suit.SPADE, rank=Rank.TWO)
        joker = Card(suit=Suit.JOKER)

        assert three.strength() == 1  # Weakest
        assert two.strength() == 13  # Strongest normal card
        assert joker.strength() > two.strength()  # Joker is always strongest

    def test_strength_revolution(self):
        """Test card strength in revolution order."""
        three = Card(suit=Suit.SPADE, rank=Rank.THREE)
        two = Card(suit=Suit.SPADE, rank=Rank.TWO)
        joker = Card(suit=Suit.JOKER)

        # In revolution, order is reversed
        assert three.strength(revolution=True) == 13  # Strongest
        assert two.strength(revolution=True) == 1  # Weakest
        # Joker is still strongest
        assert joker.strength(revolution=True) > three.strength(revolution=True)

    def test_card_string(self):
        """Test card string representation."""
        spade_ace = Card(suit=Suit.SPADE, rank=Rank.ACE)
        joker = Card(suit=Suit.JOKER)

        assert "A" in str(spade_ace)
        assert "Joker" in str(joker)

    def test_card_equality(self):
        """Test card equality (frozen model)."""
        card1 = Card(suit=Suit.SPADE, rank=Rank.ACE)
        card2 = Card(suit=Suit.SPADE, rank=Rank.ACE)
        card3 = Card(suit=Suit.HEART, rank=Rank.ACE)

        assert card1 == card2
        assert card1 != card3

    def test_card_hashable(self):
        """Test that cards can be used in sets."""
        card1 = Card(suit=Suit.SPADE, rank=Rank.ACE)
        card2 = Card(suit=Suit.SPADE, rank=Rank.ACE)

        card_set = {card1, card2}
        assert len(card_set) == 1  # Same card, only one in set


class TestCardSet:
    """Tests for CardSet class."""

    def test_empty_set(self):
        """Test empty card set."""
        cs = CardSet()
        assert cs.is_empty()
        assert cs.count() == 0

    def test_add_remove(self):
        """Test adding and removing cards."""
        cs = CardSet()
        card = Card(suit=Suit.SPADE, rank=Rank.ACE)

        cs.add(card)
        assert cs.count() == 1
        assert cs.contains(card)

        cs.remove(card)
        assert cs.count() == 0
        assert not cs.contains(card)

    def test_has_joker(self):
        """Test joker detection."""
        cs = CardSet()
        assert not cs.has_joker()

        cs.add(Card(suit=Suit.SPADE, rank=Rank.ACE))
        assert not cs.has_joker()

        cs.add(Card(suit=Suit.JOKER))
        assert cs.has_joker()

    def test_cards_by_rank(self):
        """Test filtering cards by rank."""
        cs = CardSet()
        cs.add(Card(suit=Suit.SPADE, rank=Rank.ACE))
        cs.add(Card(suit=Suit.HEART, rank=Rank.ACE))
        cs.add(Card(suit=Suit.SPADE, rank=Rank.TWO))

        aces = cs.cards_by_rank(Rank.ACE)
        assert len(aces) == 2

    def test_cards_by_suit(self):
        """Test filtering cards by suit."""
        cs = CardSet()
        cs.add(Card(suit=Suit.SPADE, rank=Rank.ACE))
        cs.add(Card(suit=Suit.SPADE, rank=Rank.TWO))
        cs.add(Card(suit=Suit.HEART, rank=Rank.ACE))

        spades = cs.cards_by_suit(Suit.SPADE)
        assert len(spades) == 2

    def test_set_operations(self):
        """Test set union, intersection, difference."""
        cs1 = CardSet()
        cs1.add(Card(suit=Suit.SPADE, rank=Rank.ACE))
        cs1.add(Card(suit=Suit.HEART, rank=Rank.ACE))

        cs2 = CardSet()
        cs2.add(Card(suit=Suit.HEART, rank=Rank.ACE))
        cs2.add(Card(suit=Suit.DIAMOND, rank=Rank.ACE))

        # Union
        union = cs1 | cs2
        assert union.count() == 3

        # Intersection
        intersection = cs1 & cs2
        assert intersection.count() == 1

        # Difference
        diff = cs1 - cs2
        assert diff.count() == 1

    def test_copy(self):
        """Test copying card set."""
        cs = CardSet()
        cs.add(Card(suit=Suit.SPADE, rank=Rank.ACE))

        copy = cs.copy()
        copy.add(Card(suit=Suit.HEART, rank=Rank.ACE))

        # Original should be unchanged
        assert cs.count() == 1
        assert copy.count() == 2


class TestCreateFullDeck:
    """Tests for create_full_deck function."""

    def test_deck_size(self):
        """Test that full deck has 53 cards."""
        deck = create_full_deck()
        assert deck.count() == 53

    def test_deck_has_joker(self):
        """Test that deck contains joker."""
        deck = create_full_deck()
        assert deck.has_joker()

    def test_deck_has_all_suits(self):
        """Test that deck has all suits."""
        deck = create_full_deck()

        for suit in [Suit.SPADE, Suit.HEART, Suit.DIAMOND, Suit.CLUB]:
            cards = deck.cards_by_suit(suit)
            assert len(cards) == 13

    def test_deck_has_all_ranks(self):
        """Test that deck has all ranks."""
        deck = create_full_deck()

        for rank in Rank:
            cards = deck.cards_by_rank(rank)
            assert len(cards) == 4  # One for each suit
