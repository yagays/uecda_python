"""Base strategy class for UECda client.

Defines the interface that all AI strategies must implement.
"""

from abc import ABC, abstractmethod

from uecda_client.game.state import GameState
from uecda_client.network.protocol import TableArray


class Strategy(ABC):
    """Abstract base class for game strategies.

    All AI implementations must inherit from this class
    and implement the required methods.
    """

    @abstractmethod
    def select_lead(
        self, my_cards: TableArray, state: GameState
    ) -> TableArray:
        """Select cards to play when leading (field is empty).

        Corresponds to C: lead() / leadRev()

        Args:
            my_cards: Current hand as TableArray
            state: Current game state

        Returns:
            TableArray with selected cards to play
        """
        pass

    @abstractmethod
    def select_follow(
        self, my_cards: TableArray, state: GameState
    ) -> TableArray:
        """Select cards to play when following (field has cards).

        Corresponds to C: follow() / followRev()

        Args:
            my_cards: Current hand as TableArray
            state: Current game state

        Returns:
            TableArray with selected cards to play (empty = pass)
        """
        pass

    @abstractmethod
    def select_exchange(
        self, my_cards: TableArray, num_cards: int
    ) -> TableArray:
        """Select cards to exchange at start of game.

        Corresponds to C: change()

        Args:
            my_cards: Current hand as TableArray
            num_cards: Number of cards to exchange (1 or 2)

        Returns:
            TableArray with cards to give away
        """
        pass

    def select_play(
        self, my_cards: TableArray, state: GameState
    ) -> TableArray:
        """Select cards to play based on current state.

        Dispatches to select_lead or select_follow based on state.onset.

        Args:
            my_cards: Current hand as TableArray
            state: Current game state

        Returns:
            TableArray with selected cards to play
        """
        if state.onset:
            return self.select_lead(my_cards, state)
        else:
            return self.select_follow(my_cards, state)
