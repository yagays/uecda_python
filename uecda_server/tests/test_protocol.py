"""Tests for protocol module."""

import struct

import pytest

from uecda_server.models.card import Card, CardSet, Rank, Suit
from uecda_server.network.protocol import (
    TABLE_BYTES,
    TableArray,
    bytes_to_int,
    create_profile_table,
    int_to_bytes,
    parse_profile_table,
)


class TestTableArray:
    """Tests for TableArray class."""

    def test_init_zeros(self):
        """Test that new table is all zeros."""
        table = TableArray()
        for i in range(8):
            for j in range(15):
                assert table.get(i, j) == 0

    def test_set_get(self):
        """Test setting and getting values."""
        table = TableArray()
        table.set(3, 7, 42)
        assert table.get(3, 7) == 42

    def test_clear(self):
        """Test clearing table."""
        table = TableArray()
        table.set(3, 7, 42)
        table.clear()
        assert table.get(3, 7) == 0

    def test_set_cards_normal(self):
        """Test setting normal cards."""
        cards = CardSet()
        cards.add(Card(suit=Suit.SPADE, rank=Rank.ACE))
        cards.add(Card(suit=Suit.HEART, rank=Rank.THREE))

        table = TableArray()
        table.set_cards(cards)

        # Spade Ace at [0][12]
        assert table.get(Suit.SPADE, Rank.ACE) == 1
        # Heart 3 at [1][1]
        assert table.get(Suit.HEART, Rank.THREE) == 1
        # Other positions should be 0
        assert table.get(Suit.SPADE, Rank.THREE) == 0

    def test_set_cards_joker(self):
        """Test setting joker."""
        cards = CardSet()
        cards.add(Card(suit=Suit.JOKER))

        table = TableArray()
        table.set_cards(cards)

        # Joker at [4][1] with value 2
        assert table.get(Suit.JOKER, 1) == 2

    def test_get_cards_normal(self):
        """Test extracting normal cards."""
        table = TableArray()
        table.set(Suit.SPADE, Rank.ACE, 1)
        table.set(Suit.HEART, Rank.THREE, 1)

        cards = table.get_cards()
        assert cards.count() == 2
        assert Card(suit=Suit.SPADE, rank=Rank.ACE) in cards
        assert Card(suit=Suit.HEART, rank=Rank.THREE) in cards

    def test_get_cards_joker(self):
        """Test extracting joker."""
        table = TableArray()
        table.set(Suit.JOKER, 1, 2)

        cards = table.get_cards()
        assert cards.count() == 1
        assert cards.has_joker()

    def test_roundtrip_cards(self):
        """Test cards survive roundtrip through table."""
        original = CardSet()
        original.add(Card(suit=Suit.SPADE, rank=Rank.ACE))
        original.add(Card(suit=Suit.DIAMOND, rank=Rank.FIVE))
        original.add(Card(suit=Suit.JOKER))

        table = TableArray()
        table.set_cards(original)
        restored = table.get_cards()

        assert restored.count() == original.count()
        for card in original:
            assert card in restored

    def test_to_bytes_size(self):
        """Test serialization produces correct size."""
        table = TableArray()
        data = table.to_bytes()
        assert len(data) == TABLE_BYTES  # 480 bytes

    def test_from_bytes_size_check(self):
        """Test deserialization checks size."""
        with pytest.raises(ValueError):
            TableArray.from_bytes(b"short")

    def test_roundtrip_bytes(self):
        """Test table survives roundtrip through bytes."""
        table = TableArray()
        table.set(0, 1, 1)
        table.set(4, 1, 2)
        table.set(5, 3, 99)
        table.set(6, 10, 3)

        data = table.to_bytes()
        restored = TableArray.from_bytes(data)

        for i in range(8):
            for j in range(15):
                assert table.get(i, j) == restored.get(i, j)

    def test_network_byte_order(self):
        """Test that bytes are in network order (big-endian)."""
        table = TableArray()
        table.set(0, 0, 0x12345678)

        data = table.to_bytes()
        # First 4 bytes should be big-endian
        assert data[0:4] == struct.pack("!I", 0x12345678)


class TestProfileTable:
    """Tests for profile table functions."""

    def test_create_profile(self):
        """Test creating profile table."""
        table = create_profile_table(20070, "TestPlayer")

        assert table.get(0, 0) == 20070
        # Check name
        assert table.get(1, 0) == ord("T")
        assert table.get(1, 1) == ord("e")

    def test_parse_profile(self):
        """Test parsing profile table."""
        table = TableArray()
        table.set(0, 0, 20070)
        name = "TestPlayer"
        for i, c in enumerate(name):
            table.set(1, i, ord(c))
        table.set(1, len(name), 0)  # Null terminate

        version, parsed_name = parse_profile_table(table)
        assert version == 20070
        assert parsed_name == "TestPlayer"

    def test_profile_roundtrip(self):
        """Test profile survives create/parse roundtrip."""
        original_name = "AI_Player"
        original_version = 20070

        table = create_profile_table(original_version, original_name)
        version, name = parse_profile_table(table)

        assert version == original_version
        assert name == original_name


class TestIntSerialization:
    """Tests for integer serialization."""

    def test_int_to_bytes(self):
        """Test integer serialization."""
        data = int_to_bytes(42)
        assert len(data) == 4
        assert data == struct.pack("!I", 42)

    def test_bytes_to_int(self):
        """Test integer deserialization."""
        data = struct.pack("!I", 12345)
        assert bytes_to_int(data) == 12345

    def test_int_roundtrip(self):
        """Test integer survives roundtrip."""
        for value in [0, 1, 9, 42, 100, 65535, 2**31 - 1]:
            assert bytes_to_int(int_to_bytes(value)) == value

    def test_negative_becomes_zero(self):
        """Test that negative values become zero."""
        data = int_to_bytes(-5)
        assert bytes_to_int(data) == 0
