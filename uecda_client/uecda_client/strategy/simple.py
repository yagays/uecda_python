"""Simple strategy implementation.

Corresponds to C implementation: daihinmin.c
- lead() / leadRev()
- follow() / followRev()
- change()

Strategy:
- Lead: Play sequences > groups > singles, prefer more cards, lowest rank
- Lead (revolution): Same but highest rank
- Follow: Match field pattern, play lowest valid cards
- Follow (revolution): Same but highest valid cards
- Exchange: Give away lowest cards
"""

from uecda_client.game.state import GameState
from uecda_client.network.protocol import TableArray
from uecda_client.strategy.analyzer import (
    cards_diff,
    cards_or,
    clear_table,
    high_cards,
    high_group,
    high_sequence,
    high_solo,
    lock_cards,
    low_cards,
    low_group,
    low_sequence,
    low_solo,
    make_group_table,
    make_jgroup_table,
    make_jkaidan_table,
    make_kaidan_table,
    n_cards,
    remove_group,
    remove_sequence,
)
from uecda_client.strategy.base import Strategy


class SimpleStrategy(Strategy):
    """Simple AI strategy matching the C reference implementation.

    Strategy overview:
    - Prioritize playing more cards at once (sequences > groups > singles)
    - When leading: play weakest valid combination
    - When following: play weakest valid combination that beats the field
    - During revolution: reverse weak/strong logic
    """

    def select_lead(
        self, my_cards: TableArray, state: GameState
    ) -> TableArray:
        """Select cards when leading (field is empty).

        Priority: longest sequence > largest group > single
        Direction: lowest to highest (or reversed if revolution)
        """
        if state.rev:
            return self._lead_rev(my_cards, state)
        else:
            return self._lead_normal(my_cards, state)

    def select_follow(
        self, my_cards: TableArray, state: GameState
    ) -> TableArray:
        """Select cards to follow the field.

        Must match pattern (single/group/sequence) and beat current rank.
        """
        if state.rev:
            return self._follow_rev(my_cards, state)
        else:
            return self._follow_normal(my_cards, state)

    def select_exchange(
        self, my_cards: TableArray, num_cards: int
    ) -> TableArray:
        """Select cards to exchange (give to opponent).

        Strategy: Give away lowest cards.

        Corresponds to C: change()
        """
        out_cards = TableArray()
        temp_cards = TableArray()

        # Copy my cards to work with
        for i in range(5):
            for j in range(15):
                temp_cards.data[i][j] = my_cards.data[i][j]

        count = 0
        while count < num_cards:
            one_card = TableArray()
            low_solo(one_card, temp_cards, use_joker=False)
            cards_diff(temp_cards, one_card)
            cards_or(out_cards, one_card)
            count += 1

        return out_cards

    def _lead_normal(self, my_cards: TableArray, state: GameState) -> TableArray:
        """Lead with lowest cards, prioritizing more cards.

        Corresponds to C: lead()
        """
        out_cards = TableArray()
        group = TableArray()
        sequence = TableArray()
        temp = TableArray()

        # Build analysis tables
        if state.joker:
            make_jgroup_table(group, my_cards, True)
            make_jkaidan_table(sequence, my_cards, True)
        else:
            make_group_table(group, my_cards)
            make_kaidan_table(sequence, my_cards)

        # Try sequences (longest first)
        find_flag = False
        for n in range(15, 2, -1):
            if n_cards(temp, sequence, n):
                low_sequence(out_cards, my_cards, temp)
                find_flag = True
                break

        # Try groups (largest first)
        if not find_flag:
            for n in range(5, 1, -1):
                if n_cards(temp, group, n):
                    low_group(out_cards, my_cards, temp, state.joker)
                    find_flag = True
                    break

        # Single card
        if not find_flag:
            low_solo(out_cards, my_cards, state.joker)

        return out_cards

    def _lead_rev(self, my_cards: TableArray, state: GameState) -> TableArray:
        """Lead during revolution with highest cards.

        Corresponds to C: leadRev()
        """
        out_cards = TableArray()
        group = TableArray()
        sequence = TableArray()
        temp = TableArray()

        # Build analysis tables
        if state.joker:
            make_jgroup_table(group, my_cards, True)
            make_jkaidan_table(sequence, my_cards, True)
        else:
            make_group_table(group, my_cards)
            make_kaidan_table(sequence, my_cards)

        # Try sequences (longest first)
        find_flag = False
        for n in range(15, 2, -1):
            if n_cards(temp, sequence, n):
                high_sequence(out_cards, my_cards, temp)
                find_flag = True
                break

        # Try groups
        if not find_flag:
            for n in range(5, 1, -1):
                if n_cards(temp, group, n):
                    high_group(out_cards, my_cards, temp, state.joker)
                    find_flag = True
                    break

        # Single card
        if not find_flag:
            high_solo(out_cards, my_cards, state.joker)

        return out_cards

    def _follow_normal(self, my_cards: TableArray, state: GameState) -> TableArray:
        """Follow the field with lowest valid cards.

        Corresponds to C: follow()
        """
        out_cards = TableArray()
        clear_table(out_cards)

        if state.qty == 1:
            self._follow_solo(out_cards, my_cards, state)
        elif state.sequence:
            self._follow_sequence(out_cards, my_cards, state)
        else:
            self._follow_group(out_cards, my_cards, state)

        return out_cards

    def _follow_rev(self, my_cards: TableArray, state: GameState) -> TableArray:
        """Follow during revolution with highest valid cards.

        Corresponds to C: followRev()
        """
        out_cards = TableArray()
        clear_table(out_cards)

        if state.qty == 1:
            self._follow_solo_rev(out_cards, my_cards, state)
        elif state.sequence:
            self._follow_sequence_rev(out_cards, my_cards, state)
        else:
            self._follow_group_rev(out_cards, my_cards, state)

        return out_cards

    def _follow_solo(
        self, out_cards: TableArray, my_cards: TableArray, state: GameState
    ) -> None:
        """Follow with single card.

        Corresponds to C: followSolo()
        """
        group = TableArray()
        sequence = TableArray()
        temp = TableArray()
        temp2 = TableArray()

        # Build analysis tables (to avoid breaking up combos)
        make_group_table(group, my_cards)
        make_kaidan_table(sequence, my_cards)

        # Remove sequences and groups
        remove_sequence(temp, my_cards, sequence)
        remove_group(temp2, temp, group)

        # Get cards stronger than field
        high_cards(temp, temp2, state.ord)

        # Apply lock
        if state.lock:
            lock_cards(temp, state.suit)

        # Pick lowest
        low_solo(out_cards, temp, state.joker)

    def _follow_solo_rev(
        self, out_cards: TableArray, my_cards: TableArray, state: GameState
    ) -> None:
        """Follow with single card during revolution.

        Corresponds to C: followSoloRev()
        """
        group = TableArray()
        sequence = TableArray()
        temp = TableArray()
        temp2 = TableArray()

        make_group_table(group, my_cards)
        make_kaidan_table(sequence, my_cards)

        remove_sequence(temp, my_cards, sequence)
        remove_group(temp2, temp, group)

        # Get cards weaker than field (revolution)
        low_cards(temp, temp2, state.ord)

        if state.lock:
            lock_cards(temp, state.suit)

        # Pick highest (revolution)
        high_solo(out_cards, temp, state.joker)

    def _follow_group(
        self, out_cards: TableArray, my_cards: TableArray, state: GameState
    ) -> None:
        """Follow with group (pair, triple, etc).

        Corresponds to C: followGroup()
        """
        group = TableArray()
        ngroup = TableArray()
        temp = TableArray()

        # Get stronger cards
        high_cards(temp, my_cards, state.ord)

        if state.lock:
            lock_cards(temp, state.suit)

        # Find groups of same size
        make_group_table(group, temp)
        if not n_cards(ngroup, group, state.qty) and state.joker:
            # Try with joker
            make_jgroup_table(group, temp, True)
            n_cards(ngroup, group, state.qty)

        low_group(out_cards, my_cards, ngroup, state.joker, state.lock, state.suit)

    def _follow_group_rev(
        self, out_cards: TableArray, my_cards: TableArray, state: GameState
    ) -> None:
        """Follow with group during revolution.

        Corresponds to C: followGroupRev()
        """
        group = TableArray()
        ngroup = TableArray()
        temp = TableArray()

        # Get weaker cards (revolution)
        low_cards(temp, my_cards, state.ord)

        if state.lock:
            lock_cards(temp, state.suit)

        make_group_table(group, temp)
        if not n_cards(ngroup, group, state.qty) and state.joker:
            make_jgroup_table(group, temp, True)
            n_cards(ngroup, group, state.qty)

        high_group(out_cards, my_cards, ngroup, state.joker, state.lock, state.suit)

    def _follow_sequence(
        self, out_cards: TableArray, my_cards: TableArray, state: GameState
    ) -> None:
        """Follow with sequence.

        Corresponds to C: followSequence()
        """
        seq = TableArray()
        nseq = TableArray()
        temp = TableArray()

        # Get stronger cards
        high_cards(temp, my_cards, state.ord)

        if state.lock:
            lock_cards(temp, state.suit)

        # Find sequences of same length
        make_kaidan_table(seq, temp)
        if not n_cards(nseq, seq, state.qty) and state.joker:
            make_jkaidan_table(seq, temp, True)
            n_cards(nseq, seq, state.qty)

        low_sequence(out_cards, my_cards, nseq)

    def _follow_sequence_rev(
        self, out_cards: TableArray, my_cards: TableArray, state: GameState
    ) -> None:
        """Follow with sequence during revolution.

        Corresponds to C: followSequenceRev()
        """
        seq = TableArray()
        nseq = TableArray()
        temp = TableArray()

        # Get weaker cards (revolution)
        low_cards(temp, my_cards, state.ord)

        if state.lock:
            lock_cards(temp, state.suit)

        make_kaidan_table(seq, temp)
        if not n_cards(nseq, seq, state.qty) and state.joker:
            make_jkaidan_table(seq, temp, True)
            n_cards(nseq, seq, state.qty)

        high_sequence(out_cards, my_cards, nseq)
