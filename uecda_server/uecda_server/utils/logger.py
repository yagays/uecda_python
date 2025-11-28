"""Logging utilities and game state display."""

import logging
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uecda_server.models.card import CardSet
    from uecda_server.models.game_state import GameState
    from uecda_server.models.player import Player


def setup_logging(level: str = "INFO") -> None:
    """Configure logging for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


class GameDisplay:
    """Display game state to stdout."""

    def __init__(self, show_hands: bool = False):
        """Initialize display.

        Args:
            show_hands: Whether to show player hands
        """
        self.show_hands = show_hands

    def print_separator(self) -> None:
        """Print a separator line."""
        print("=" * 60)

    def print_game_start(self, game_number: int, num_games: int) -> None:
        """Print game start message."""
        self.print_separator()
        print(f"GAME {game_number}/{num_games}")
        self.print_separator()

    def print_turn(
        self,
        turn_number: int,
        player: "Player",
        state: "GameState",
    ) -> None:
        """Print turn information."""
        status = []
        if state.is_revolution:
            status.append("REVOLUTION")
        if state.is_eleven_back:
            status.append("11-BACK")
        if state.field.is_locked:
            status.append("LOCK")

        status_str = f" [{', '.join(status)}]" if status else ""
        print(f"\nTurn {turn_number}: Player {player.player_id} ({player.name}){status_str}")
        print(f"Field: {state.field}")

    def print_move(
        self,
        player: "Player",
        cards: "CardSet",
        is_pass: bool,
    ) -> None:
        """Print player's move."""
        if is_pass:
            print("  -> PASS")
        else:
            print(f"  -> Played: {cards}")

    def print_hand_counts(
        self,
        players: list["Player"],
        hands: list["CardSet"],
    ) -> None:
        """Print hand counts for all players."""
        counts = [f"P{p.player_id}:{hands[p.player_id].count()}" for p in players]
        print(f"Hand counts: {' | '.join(counts)}")

    def print_hands(
        self,
        players: list["Player"],
        hands: list["CardSet"],
    ) -> None:
        """Print hands for all players (if show_hands is enabled)."""
        if not self.show_hands:
            return

        print("\nHands:")
        for player in players:
            if player.has_finished:
                print(f"  P{player.player_id}: [FINISHED]")
            else:
                print(f"  P{player.player_id}: {hands[player.player_id]}")

    def print_game_end(
        self,
        game_number: int,
        finish_order: list[int],
        players: list["Player"],
    ) -> None:
        """Print game end results."""
        print(f"\nGame {game_number} finished!")
        print("Results:")
        rank_names = ["1st (大富豪)", "2nd (富豪)", "3rd (平民)", "4th (貧民)", "5th (大貧民)"]
        for rank, player_id in enumerate(finish_order):
            player = players[player_id]
            print(f"  {rank_names[rank]}: Player {player_id} ({player.name})")

    def print_final_results(
        self,
        points: dict[int, int],
        players: list["Player"],
    ) -> None:
        """Print final tournament results."""
        self.print_separator()
        print("FINAL RESULTS")
        self.print_separator()

        # Sort by points descending
        sorted_players = sorted(points.items(), key=lambda x: x[1], reverse=True)

        for rank, (player_id, pts) in enumerate(sorted_players, 1):
            player = players[player_id]
            print(f"  #{rank}: Player {player_id} ({player.name}) - {pts} points")

    def print_player_connected(self, player_id: int, name: str) -> None:
        """Print player connection message."""
        print(f"Player {player_id} connected: {name}")

    def print_waiting_for_players(self, current: int, total: int) -> None:
        """Print waiting message."""
        print(f"Waiting for players... ({current}/{total})")

    def print_all_connected(self, players: list["Player"]) -> None:
        """Print all players connected message."""
        print("\nAll players connected:")
        for player in players:
            print(f"  Player {player.player_id}: {player.name}")
        print()
