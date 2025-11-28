"""Hand analyzer for detecting groups and sequences.

Corresponds to C implementation: daihinmin.c
- makeGroupTable, makeJGroupTable
- makeKaidanTable, makeJKaidanTable
- Various helper functions
"""

from uecda_client.network.protocol import TABLE_COLS, TABLE_ROWS, TableArray


def clear_table(table: TableArray) -> None:
    """Clear all values in table to 0."""
    for i in range(TABLE_ROWS):
        for j in range(TABLE_COLS):
            table.data[i][j] = 0


def clear_cards(table: TableArray) -> None:
    """Clear card rows (0-4) to 0."""
    for i in range(5):
        for j in range(TABLE_COLS):
            table.data[i][j] = 0


def copy_table(dest: TableArray, src: TableArray) -> None:
    """Copy src table to dest table."""
    for i in range(TABLE_ROWS):
        for j in range(TABLE_COLS):
            dest.data[i][j] = src.data[i][j]


def copy_cards(dest: TableArray, src: TableArray) -> None:
    """Copy card rows (0-4) from src to dest."""
    for i in range(5):
        for j in range(TABLE_COLS):
            dest.data[i][j] = src.data[i][j]


def is_empty_cards(cards: TableArray) -> bool:
    """Check if card table is empty.

    Corresponds to C: beEmptyCards()
    """
    for i in range(5):
        for j in range(TABLE_COLS):
            if cards.data[i][j] > 0:
                return False
    return True


def count_cards(cards: TableArray) -> int:
    """Count number of cards in table.

    Corresponds to C: qtyOfCards()
    """
    count = 0
    for i in range(5):
        for j in range(TABLE_COLS):
            if cards.data[i][j] > 0:
                count += 1
    return count


def cards_or(cards1: TableArray, cards2: TableArray) -> None:
    """OR cards2 into cards1 (add cards from cards2 to cards1).

    Corresponds to C: cardsOr()
    """
    for i in range(TABLE_COLS):
        for j in range(5):
            if cards2.data[j][i] > 0:
                cards1.data[j][i] = 1


def cards_and(cards1: TableArray, cards2: TableArray) -> None:
    """AND cards1 with cards2 (keep only common cards).

    Corresponds to C: cardsAnd()
    """
    for i in range(TABLE_COLS):
        for j in range(5):
            if cards1.data[j][i] == 1 and cards2.data[j][i] == 1:
                cards1.data[j][i] = 1
            else:
                cards1.data[j][i] = 0


def cards_diff(cards1: TableArray, cards2: TableArray) -> None:
    """Remove cards in cards2 from cards1.

    Corresponds to C: cardsDiff()
    """
    for i in range(TABLE_COLS):
        for j in range(5):
            if cards2.data[j][i] == 1:
                cards1.data[j][i] = 0


def make_group_table(tgt_cards: TableArray, my_cards: TableArray) -> None:
    """Analyze hand for groups (pairs, triples, etc).

    For each rank, stores the count of cards if >= 2.

    Corresponds to C: makeGroupTable()

    Args:
        tgt_cards: Output table (stores group counts at card positions)
        my_cards: Input hand table
    """
    clear_table(tgt_cards)

    for i in range(TABLE_COLS):  # Each rank
        count = sum(my_cards.data[j][i] for j in range(4))  # Count suits 0-3
        if count > 1:  # 2 or more cards of same rank
            for j in range(4):
                if my_cards.data[j][i] == 1:
                    tgt_cards.data[j][i] = count


def make_jgroup_table(
    tgt_cards: TableArray, my_cards: TableArray, has_joker: bool
) -> None:
    """Analyze hand for groups including joker.

    Corresponds to C: makeJGroupTable()

    Args:
        tgt_cards: Output table
        my_cards: Input hand table
        has_joker: Whether we have joker
    """
    clear_table(tgt_cards)

    if not has_joker:
        return

    for i in range(14):  # Each rank (excluding joker column)
        count = sum(my_cards.data[j][i] for j in range(4)) + 1  # +1 for joker
        if count > 1:
            for j in range(4):
                if my_cards.data[j][i] == 1:
                    tgt_cards.data[j][i] = count


def make_kaidan_table(tgt_cards: TableArray, my_cards: TableArray) -> None:
    """Analyze hand for sequences (straights).

    For each starting position, stores the sequence length if >= 3.

    Corresponds to C: makeKaidanTable()

    Args:
        tgt_cards: Output table (stores sequence lengths)
        my_cards: Input hand table
    """
    clear_table(tgt_cards)

    for suit in range(4):  # Each suit
        count = 0
        for rank in range(13, 0, -1):  # High to low (13=2 down to 1=3)
            if my_cards.data[suit][rank] == 1:
                count += 1
            else:
                count = 0

            if count >= 3:
                tgt_cards.data[suit][rank] = count
            else:
                tgt_cards.data[suit][rank] = 0


def make_jkaidan_table(
    tgt_cards: TableArray, my_cards: TableArray, has_joker: bool
) -> None:
    """Analyze hand for sequences including joker.

    Joker can fill one gap in sequence.

    Corresponds to C: makeJKaidanTable()

    Args:
        tgt_cards: Output table
        my_cards: Input hand table
        has_joker: Whether we have joker
    """
    clear_table(tgt_cards)

    if not has_joker:
        return

    for suit in range(4):
        count = 1  # Start with joker
        no_j_count = 0  # Count without joker gap

        for rank in range(13, -1, -1):  # High to low
            if my_cards.data[suit][rank] == 1:
                count += 1
                no_j_count += 1
            else:
                # Card missing - joker can fill first gap
                count = no_j_count + 1  # Sequence length with joker at gap
                no_j_count = 0

            if count > 2:
                tgt_cards.data[suit][rank] = count
            else:
                tgt_cards.data[suit][rank] = 0


def low_cards(out_cards: TableArray, my_cards: TableArray, threshold: int) -> None:
    """Get cards below threshold rank.

    Corresponds to C: lowCards()

    Args:
        out_cards: Output table
        my_cards: Input hand table
        threshold: Rank threshold (exclusive upper bound)
    """
    copy_table(out_cards, my_cards)
    for rank in range(threshold, TABLE_COLS):
        for suit in range(4):
            out_cards.data[suit][rank] = 0


def high_cards(out_cards: TableArray, my_cards: TableArray, threshold: int) -> None:
    """Get cards above threshold rank.

    Corresponds to C: highCards()

    Args:
        out_cards: Output table
        my_cards: Input hand table
        threshold: Rank threshold (exclusive lower bound)
    """
    copy_table(out_cards, my_cards)
    for rank in range(threshold + 1):
        for suit in range(4):
            out_cards.data[suit][rank] = 0


def n_cards(n_cards_out: TableArray, target: TableArray, n: int) -> bool:
    """Extract cards with exactly n count from target table.

    Corresponds to C: nCards()

    Args:
        n_cards_out: Output table (cards with count == n)
        target: Input analysis table (group or sequence table)
        n: Target count

    Returns:
        True if any cards found, False otherwise
    """
    found = False
    clear_table(n_cards_out)

    for suit in range(4):
        for rank in range(TABLE_COLS):
            if target.data[suit][rank] == n:
                n_cards_out.data[suit][rank] = n
                found = True
            else:
                n_cards_out.data[suit][rank] = 0

    return found


def lock_cards(target_cards: TableArray, suit_mask: list[int]) -> None:
    """Keep only cards matching the locked suits.

    Corresponds to C: lockCards()

    Args:
        target_cards: Table to filter in place
        suit_mask: suit[i]=1 means suit i is allowed
    """
    for suit in range(4):
        for rank in range(TABLE_COLS):
            target_cards.data[suit][rank] *= suit_mask[suit]


def low_group(
    out_cards: TableArray,
    my_cards: TableArray,
    group: TableArray,
    has_joker: bool = False,
    is_locked: bool = False,
    suit_mask: list[int] | None = None,
) -> None:
    """Find lowest group from group analysis table.

    Corresponds to C: lowGroup()

    Args:
        out_cards: Output table with selected cards
        my_cards: My hand table
        group: Group analysis table
        has_joker: Whether I have joker
        is_locked: Whether lock (shibari) is active
        suit_mask: Allowed suits if locked
    """
    clear_table(out_cards)
    count = 0
    qty = 0

    # Find lowest rank with group
    for rank in range(1, 14):
        for suit in range(4):
            if group.data[suit][rank] > 1:
                out_cards.data[suit][rank] = 1
                count += 1
                qty = group.data[suit][rank]
        if count > 0:
            break

    if count == 0:
        return

    # Fill remaining slots with joker if needed
    rank_found = -1
    for rank in range(1, 14):
        if out_cards.data[0][rank] or out_cards.data[1][rank] or \
           out_cards.data[2][rank] or out_cards.data[3][rank]:
            rank_found = rank
            break

    if rank_found >= 0 and count < qty:
        for suit in range(4):
            if count >= qty:
                break
            if my_cards.data[suit][rank_found] == 0:
                if not is_locked or (suit_mask and suit_mask[suit] == 1):
                    out_cards.data[suit][rank_found] = 2  # Joker marker
                    count += 1


def high_group(
    out_cards: TableArray,
    my_cards: TableArray,
    group: TableArray,
    has_joker: bool = False,
    is_locked: bool = False,
    suit_mask: list[int] | None = None,
) -> None:
    """Find highest group from group analysis table.

    Corresponds to C: highGroup()
    """
    clear_table(out_cards)
    count = 0
    qty = 0

    # Find highest rank with group
    for rank in range(13, 0, -1):
        for suit in range(4):
            if group.data[suit][rank] > 1:
                out_cards.data[suit][rank] = 1
                count += 1
                qty = group.data[suit][rank]
        if count > 0:
            break

    if count == 0:
        return

    # Fill remaining with joker
    rank_found = -1
    for rank in range(13, 0, -1):
        if out_cards.data[0][rank] or out_cards.data[1][rank] or \
           out_cards.data[2][rank] or out_cards.data[3][rank]:
            rank_found = rank
            break

    if rank_found >= 0 and count < qty:
        for suit in range(4):
            if count >= qty:
                break
            if my_cards.data[suit][rank_found] == 0:
                if not is_locked or (suit_mask and suit_mask[suit] == 1):
                    out_cards.data[suit][rank_found] = 2
                    count += 1


def low_sequence(
    out_cards: TableArray, my_cards: TableArray, sequence: TableArray
) -> None:
    """Find lowest sequence from sequence analysis table.

    Corresponds to C: lowSequence()
    """
    clear_table(out_cards)
    low_value = 0
    low_line = 0
    low_column = 0

    # Find lowest starting sequence
    col = 0
    while col < TABLE_COLS and low_value == 0:
        for suit in range(4):
            if sequence.data[suit][col] != 0:
                if sequence.data[suit][col] > low_value:
                    low_value = sequence.data[suit][col]
                    low_line = suit
                    low_column = col
        if low_value == 0:
            col += 1

    # Output the sequence
    if low_value != 0:
        for i in range(low_column, low_column + low_value):
            if i < TABLE_COLS:
                if my_cards.data[low_line][i] == 1:
                    out_cards.data[low_line][i] = 1
                else:
                    out_cards.data[low_line][i] = 2  # Joker


def high_sequence(
    out_cards: TableArray, my_cards: TableArray, sequence: TableArray
) -> None:
    """Find highest sequence from sequence analysis table.

    Corresponds to C: highSequence()
    """
    clear_table(out_cards)
    high_value = 0
    high_line = 0
    high_column = 0

    # Find highest ending sequence
    col = 14
    while col > 0 and high_value == 0:
        for suit in range(4):
            if sequence.data[suit][col] != 0 and my_cards.data[suit][col] != 0:
                # Search backwards for longest sequence ending here
                k = -1
                while col - k >= 0:
                    if sequence.data[suit][col - k] >= high_value:
                        high_value = sequence.data[suit][col - k]
                        high_line = suit
                        high_column = col - k
                    pre_value = sequence.data[suit][col - k]
                    k += 1
                    if col - k < 0 or pre_value > sequence.data[suit][col - k]:
                        break
        if high_value == 0:
            col -= 1

    # Output the sequence
    if high_value > 0:
        for i in range(high_column, high_column + high_value):
            if i < TABLE_COLS:
                if my_cards.data[high_line][i] == 1:
                    out_cards.data[high_line][i] = 1
                else:
                    out_cards.data[high_line][i] = 2


def remove_group(
    out_cards: TableArray, my_cards: TableArray, group: TableArray
) -> None:
    """Get cards not in any group.

    Corresponds to C: removeGroup()
    """
    for rank in range(TABLE_COLS):
        for suit in range(4):
            if my_cards.data[suit][rank] == 1 and group.data[suit][rank] == 0:
                out_cards.data[suit][rank] = 1
            else:
                out_cards.data[suit][rank] = 0


def remove_sequence(
    out_cards: TableArray, my_cards: TableArray, sequence: TableArray
) -> None:
    """Get cards not in any sequence.

    Corresponds to C: removeSequence()
    """
    for suit in range(4):
        rank = 0
        while rank < TABLE_COLS:
            if my_cards.data[suit][rank] == 1 and sequence.data[suit][rank] == 0:
                out_cards.data[suit][rank] = 1
            elif sequence.data[suit][rank] > 2:
                # Skip entire sequence
                seq_len = sequence.data[suit][rank]
                for k in range(seq_len):
                    if rank + k < TABLE_COLS:
                        out_cards.data[suit][rank + k] = 0
                rank += seq_len - 1
            else:
                out_cards.data[suit][rank] = 0
            rank += 1


def low_solo(
    out_cards: TableArray, my_cards: TableArray, use_joker: bool = False
) -> None:
    """Find lowest single card.

    Corresponds to C: lowSolo()
    """
    clear_table(out_cards)
    found = False

    for rank in range(1, 14):
        if found:
            break
        for suit in range(4):
            if my_cards.data[suit][rank] == 1:
                out_cards.data[suit][rank] = 1
                found = True
                break

    if not found and use_joker:
        out_cards.data[0][14] = 2  # Joker at highest position


def high_solo(
    out_cards: TableArray, my_cards: TableArray, use_joker: bool = False
) -> None:
    """Find highest single card.

    Corresponds to C: highSolo()
    """
    clear_table(out_cards)
    found = False

    for rank in range(13, 0, -1):
        if found:
            break
        for suit in range(4):
            if my_cards.data[suit][rank] == 1:
                out_cards.data[suit][rank] = 1
                found = True
                break

    if not found and use_joker:
        out_cards.data[0][0] = 2  # Joker at lowest position (for revolution)
