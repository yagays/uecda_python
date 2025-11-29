"""Game logger for detailed game replay."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

from pydantic import BaseModel

from uecda_server.models.card import CardSet
from uecda_server.models.game_state import CardType, GameState
from uecda_server.models.player import Player, PlayerRank

from .formatters import format_cards, format_hands


class GameLogConfig(BaseModel):
    """Configuration for game logging."""

    enabled: bool = False
    output_path: str = "game_log.jsonl"


# PlayerRank to string mapping for log output
PLAYER_RANK_NAMES: dict[PlayerRank, str] = {
    PlayerRank.DAIFUGO: "daifugo",
    PlayerRank.FUGO: "fugo",
    PlayerRank.HEIMIN: "heimin",
    PlayerRank.HINMIN: "hinmin",
    PlayerRank.DAIHINMIN: "daihinmin",
}


class GameLogger:
    """Logger for detailed game events in JSONL format.

    Each line in the output file is a JSON object representing one event.
    This allows step-by-step replay of the game.
    """

    def __init__(self, config: GameLogConfig | None = None):
        """Initialize game logger.

        Args:
            config: Logging configuration. If None, logging is disabled.
        """
        self.config = config or GameLogConfig()
        self._file: TextIO | None = None

    def __enter__(self) -> "GameLogger":
        """Context manager entry."""
        if self.config.enabled and self.config.output_path:
            path = Path(self.config.output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._file = open(path, "a", encoding="utf-8")
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()

    def close(self) -> None:
        """Close the log file."""
        if self._file:
            self._file.close()
            self._file = None

    def _write(self, event: dict[str, Any]) -> None:
        """Write an event to the log file.

        Args:
            event: Event dictionary to write as JSON.
        """
        if self._file:
            self._file.write(json.dumps(event, ensure_ascii=False) + "\n")
            self._file.flush()

    def log_session_start(self, players: list[Player]) -> None:
        """Log session start with player information.

        Args:
            players: List of players in the session.
        """
        self._write({
            "type": "session_start",
            "timestamp": datetime.now().isoformat(),
            "players": [
                {"id": p.player_id, "name": p.name}
                for p in players
            ],
        })

    def log_game_start(
        self,
        game_num: int,
        hands: list[CardSet],
        players: list[Player],
        first_player: int,
    ) -> None:
        """Log game start with initial hands.

        Args:
            game_num: Game number.
            hands: List of initial hands indexed by player_id.
            players: List of players (for rank information).
            first_player: Player ID who plays first.
        """
        self._write({
            "type": "game_start",
            "game": game_num,
            "hands": format_hands(hands),
            "ranks": {
                str(p.player_id): PLAYER_RANK_NAMES[p.rank]
                for p in players
            },
            "first_player": first_player,
        })

    def log_exchange(
        self,
        game_num: int,
        exchanges: list[dict[str, Any]],
        hands_after: list[CardSet],
    ) -> None:
        """Log card exchange phase.

        Args:
            game_num: Game number.
            exchanges: List of exchange records, each containing:
                - from: Player ID giving cards
                - to: Player ID receiving cards
                - cards: CardSet being exchanged
            hands_after: Hands after exchange, indexed by player_id.
        """
        formatted_exchanges = [
            {
                "from": ex["from"],
                "to": ex["to"],
                "cards": format_cards(ex["cards"]),
            }
            for ex in exchanges
        ]
        self._write({
            "type": "exchange",
            "game": game_num,
            "exchanges": formatted_exchanges,
            "hands_after": format_hands(hands_after),
        })

    def log_turn(
        self,
        game_num: int,
        turn_num: int,
        player_id: int,
        action: str,
        cards: CardSet,
        card_type: CardType,
        field: CardSet,
        hands: list[CardSet],
        state: GameState,
    ) -> None:
        """Log a single turn.

        Args:
            game_num: Game number.
            turn_num: Turn number within the game.
            player_id: Player who took the action.
            action: "play" or "pass".
            cards: Cards played (empty if pass).
            card_type: Type of cards played.
            field: Current field state after the action.
            hands: All players' hands after the action.
            state: Game state after the action.
        """
        self._write({
            "type": "turn",
            "game": game_num,
            "turn": turn_num,
            "player": player_id,
            "action": action,
            "cards": format_cards(cards),
            "card_type": card_type.value,
            "field": format_cards(field),
            "hands": format_hands(hands),
            "state": {
                "revolution": state.is_revolution,
                "eleven_back": state.is_eleven_back,
                "locked": state.field.is_locked,
            },
        })

    def log_special(
        self,
        game_num: int,
        turn_num: int,
        event: str,
        player_id: int,
        detail: dict[str, Any] | None = None,
    ) -> None:
        """Log a special event.

        Args:
            game_num: Game number.
            turn_num: Turn number when the event occurred.
            event: Event type (e.g., "eight_stop", "revolution", "player_finish").
            player_id: Player who triggered the event.
            detail: Additional event details.
        """
        record: dict[str, Any] = {
            "type": "special",
            "game": game_num,
            "turn": turn_num,
            "event": event,
            "player": player_id,
        }
        if detail:
            record["detail"] = detail
        self._write(record)

    def log_game_end(
        self,
        game_num: int,
        finish_order: list[int],
        players: list[Player],
    ) -> None:
        """Log game end with results.

        Args:
            game_num: Game number.
            finish_order: List of player IDs in finish order.
            players: List of players with updated ranks.
        """
        self._write({
            "type": "game_end",
            "game": game_num,
            "finish_order": finish_order,
            "new_ranks": {
                str(p.player_id): PLAYER_RANK_NAMES[p.rank]
                for p in players
            },
        })

    def log_session_end(
        self,
        total_games: int,
        final_points: dict[int, int],
        ranking: list[int],
    ) -> None:
        """Log session end with final results.

        Args:
            total_games: Total number of games played.
            final_points: Dict mapping player_id to total points.
            ranking: Player IDs in ranking order (best first).
        """
        self._write({
            "type": "session_end",
            "total_games": total_games,
            "final_points": {str(k): v for k, v in final_points.items()},
            "ranking": ranking,
        })
