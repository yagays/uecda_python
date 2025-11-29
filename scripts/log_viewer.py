#!/usr/bin/env python3
"""Interactive log viewer for UECda game logs.

Usage:
    python scripts/log_viewer.py game_log.jsonl

Keys:
    n: Next step
    p: Previous step
    c: Continuous playback (1 sec interval), any key to stop
    g: Jump to game number
    t: Jump to turn number
    q: Quit
"""

import argparse
import curses
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GameState:
    """Current game state for display."""

    game: int = 0
    turn: int = 0
    players: list[dict] = field(default_factory=list)
    hands: dict[str, str] = field(default_factory=dict)
    ranks: dict[str, str] = field(default_factory=dict)
    field_cards: str = ""
    field_type: str = ""
    last_action: str = ""
    current_player: int = -1
    revolution: bool = False
    eleven_back: bool = False
    locked: bool = False
    finished_players: set[int] = field(default_factory=set)


def load_events(path: Path) -> list[dict]:
    """Load all events from JSONL file."""
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def build_states(events: list[dict]) -> list[GameState]:
    """Build displayable states from events."""
    states: list[GameState] = []
    current = GameState()

    for event in events:
        event_type = event.get("type")

        if event_type == "session_start":
            current = GameState()
            current.players = event.get("players", [])
            states.append(_copy_state(current))

        elif event_type == "game_start":
            current.game = event.get("game", 0)
            current.turn = 0
            current.hands = event.get("hands", {})
            current.ranks = event.get("ranks", {})
            current.field_cards = ""
            current.field_type = ""
            current.last_action = "Game started"
            current.current_player = event.get("first_player", 0)
            current.revolution = False
            current.eleven_back = False
            current.locked = False
            current.finished_players = set()
            states.append(_copy_state(current))

        elif event_type == "exchange":
            current.hands = event.get("hands_after", current.hands)
            exchanges = event.get("exchanges", [])
            if exchanges:
                ex_strs = []
                for ex in exchanges:
                    ex_strs.append(
                        f"Player {ex['from']} -> Player {ex['to']}: {ex['cards']}"
                    )
                current.last_action = "Exchange: " + "; ".join(ex_strs)
            states.append(_copy_state(current))

        elif event_type == "turn":
            current.game = event.get("game", current.game)
            current.turn = event.get("turn", current.turn)
            current.hands = event.get("hands", current.hands)

            player = event.get("player", 0)
            action = event.get("action", "")
            cards = event.get("cards", "")

            if action == "play":
                current.field_cards = event.get("field", "")
                current.field_type = event.get("card_type", "")
                current.last_action = f"Player {player} played {cards}"
            else:
                current.last_action = f"Player {player} passed"

            state = event.get("state", {})
            current.revolution = state.get("revolution", False)
            current.eleven_back = state.get("eleven_back", False)
            current.locked = state.get("locked", False)
            current.current_player = player

            states.append(_copy_state(current))

        elif event_type == "special":
            ev = event.get("event", "")
            player = event.get("player", -1)

            if ev == "eight_stop":
                current.last_action = f"8-stop! Player {player} cleared the field"
                current.field_cards = ""
                current.field_type = ""
            elif ev == "revolution":
                current.revolution = not current.revolution
                current.last_action = f"Revolution by Player {player}!"
            elif ev == "eleven_back":
                current.eleven_back = True
                current.last_action = f"11-back by Player {player}!"
            elif ev == "lock":
                current.locked = True
                current.last_action = f"Lock by Player {player}!"
            elif ev == "field_clear":
                current.last_action = "Field cleared (all passed)"
                current.field_cards = ""
                current.field_type = ""
                current.locked = False
                current.eleven_back = False
            elif ev == "player_finish":
                current.finished_players.add(player)
                pos = len(current.finished_players)
                current.last_action = f"Player {player} finished in position {pos}"

            states.append(_copy_state(current))

        elif event_type == "game_end":
            current.last_action = "Game ended"
            finish_order = event.get("finish_order", [])
            if finish_order:
                order_str = ", ".join(f"Player {p}" for p in finish_order)
                current.last_action = f"Game ended. Order: {order_str}"
            current.ranks = event.get("new_ranks", current.ranks)
            states.append(_copy_state(current))

        elif event_type == "session_end":
            current.last_action = "Session ended"
            points = event.get("final_points", {})
            if points:
                pts_str = ", ".join(f"P{k}:{v}" for k, v in sorted(points.items()))
                current.last_action = f"Session ended. Points: {pts_str}"
            states.append(_copy_state(current))

    return states


def _copy_state(state: GameState) -> GameState:
    """Create a copy of the game state."""
    return GameState(
        game=state.game,
        turn=state.turn,
        players=list(state.players),
        hands=dict(state.hands),
        ranks=dict(state.ranks),
        field_cards=state.field_cards,
        field_type=state.field_type,
        last_action=state.last_action,
        current_player=state.current_player,
        revolution=state.revolution,
        eleven_back=state.eleven_back,
        locked=state.locked,
        finished_players=set(state.finished_players),
    )


RANK_NAMES = {
    "daifugo": "大富豪",
    "fugo": "富豪",
    "heimin": "平民",
    "hinmin": "貧民",
    "daihinmin": "大貧民",
}


def get_player_name(state: GameState, player_id: int) -> str:
    """Get player name by ID."""
    for p in state.players:
        if p.get("id") == player_id:
            return p.get("name", f"Player {player_id}")
    return f"Player {player_id}"


def get_rank_display(state: GameState, player_id: int) -> str:
    """Get rank display for player."""
    rank = state.ranks.get(str(player_id), "heimin")
    return RANK_NAMES.get(rank, rank)


def draw_screen(stdscr, state: GameState, step: int, total: int) -> None:
    """Draw the current state to the screen."""
    stdscr.clear()
    height, width = stdscr.getmaxyx()
    width = min(width, 100)

    line = 0
    sep = "=" * 80

    # Header
    stdscr.addnstr(line, 0, sep, width - 1)
    line += 1

    # Game info line
    flags = []
    if state.revolution:
        flags.append("[REV]")
    if state.locked:
        flags.append("[LOCK]")
    if state.eleven_back:
        flags.append("[11B]")
    flags_str = " ".join(flags)

    game_info = f"Game {state.game} / Turn {state.turn}"
    step_info = f"Step {step + 1}/{total}"
    middle_space = 80 - len(game_info) - len(flags_str) - len(step_info) - 4
    header = f"{game_info}  {flags_str}{' ' * max(middle_space, 1)}{step_info}"
    stdscr.addnstr(line, 0, header, width - 1)
    line += 1

    stdscr.addnstr(line, 0, sep, width - 1)
    line += 1
    line += 1

    # Field
    if state.field_cards:
        field_line = f"Field: [{state.field_cards}] ({state.field_type})"
    else:
        field_line = "Field: (empty)"
    stdscr.addnstr(line, 0, field_line, width - 1)
    line += 1

    # Last action
    stdscr.addnstr(line, 0, f"Last: {state.last_action}", width - 1)
    line += 1
    line += 1

    # Player section
    dash_sep = "-" * 80
    stdscr.addnstr(line, 0, dash_sep, width - 1)
    line += 1

    # Draw players in 2-column layout
    num_players = len(state.players)
    col_width = 39

    for row in range((num_players + 1) // 2):
        left_id = row * 2
        right_id = row * 2 + 1

        # Player names with rank
        left_name = ""
        right_name = ""

        if left_id < num_players:
            name = get_player_name(state, left_id)
            rank = get_rank_display(state, left_id)
            marker = " <<<" if state.current_player == left_id else ""
            finished = " [済]" if left_id in state.finished_players else ""
            left_name = f"Player {left_id} ({name}) [{rank}]{finished}{marker}"

        if right_id < num_players:
            name = get_player_name(state, right_id)
            rank = get_rank_display(state, right_id)
            marker = " <<<" if state.current_player == right_id else ""
            finished = " [済]" if right_id in state.finished_players else ""
            right_name = f"Player {right_id} ({name}) [{rank}]{finished}{marker}"

        name_line = f"{left_name:<{col_width}} | {right_name}"
        stdscr.addnstr(line, 0, name_line, width - 1)
        line += 1

        # Hands
        left_hand = state.hands.get(str(left_id), "")
        right_hand = state.hands.get(str(right_id), "") if right_id < num_players else ""

        # Truncate if too long
        if len(left_hand) > col_width - 2:
            left_hand = left_hand[: col_width - 5] + "..."
        if len(right_hand) > col_width - 2:
            right_hand = right_hand[: col_width - 5] + "..."

        hand_line = f"  {left_hand:<{col_width - 2}} |   {right_hand}"
        stdscr.addnstr(line, 0, hand_line, width - 1)
        line += 1

        # Card counts
        left_count = len(left_hand.split(",")) if left_hand else 0
        right_count = len(right_hand.split(",")) if right_hand else 0
        count_line = f"  ({left_count} cards){' ' * (col_width - 12)} |   ({right_count} cards)"
        if right_id >= num_players:
            count_line = f"  ({left_count} cards)"
        stdscr.addnstr(line, 0, count_line, width - 1)
        line += 1

        stdscr.addnstr(line, 0, dash_sep, width - 1)
        line += 1

    stdscr.addnstr(line, 0, sep, width - 1)
    line += 1

    # Help line
    help_line = "[n]ext [p]rev [c]ontinuous [g]ame [t]urn [q]uit"
    stdscr.addnstr(line, 0, help_line, width - 1)

    stdscr.refresh()


def input_number(stdscr, prompt: str) -> int | None:
    """Get a number from the user."""
    height, width = stdscr.getmaxyx()
    stdscr.addnstr(height - 2, 0, prompt, width - 1)
    stdscr.clrtoeol()
    stdscr.refresh()

    curses.echo()
    curses.curs_set(1)
    try:
        inp = stdscr.getstr(height - 2, len(prompt), 10).decode("utf-8")
        return int(inp) if inp.strip() else None
    except (ValueError, curses.error):
        return None
    finally:
        curses.noecho()
        curses.curs_set(0)


def find_game_start(states: list[GameState], game_num: int) -> int | None:
    """Find the step index for the start of a game."""
    for i, s in enumerate(states):
        if s.game == game_num and s.turn == 0:
            return i
    return None


def find_turn(states: list[GameState], turn_num: int, current_game: int) -> int | None:
    """Find the step index for a specific turn in the current game."""
    for i, s in enumerate(states):
        if s.game == current_game and s.turn == turn_num:
            return i
    return None


def main_loop(stdscr, states: list[GameState]) -> None:
    """Main event loop."""
    curses.curs_set(0)
    stdscr.nodelay(False)
    stdscr.timeout(-1)

    step = 0
    total = len(states)

    while True:
        draw_screen(stdscr, states[step], step, total)

        try:
            key = stdscr.getch()
        except curses.error:
            continue

        if key == ord("q"):
            break
        elif key == ord("n"):
            if step < total - 1:
                step += 1
        elif key == ord("p"):
            if step > 0:
                step -= 1
        elif key == ord("c"):
            # Continuous playback
            stdscr.nodelay(True)
            stdscr.timeout(1000)
            while step < total - 1:
                step += 1
                draw_screen(stdscr, states[step], step, total)
                try:
                    k = stdscr.getch()
                    if k != -1:
                        break
                except curses.error:
                    pass
            stdscr.nodelay(False)
            stdscr.timeout(-1)
        elif key == ord("g"):
            num = input_number(stdscr, "Jump to game: ")
            if num is not None:
                idx = find_game_start(states, num)
                if idx is not None:
                    step = idx
        elif key == ord("t"):
            num = input_number(stdscr, "Jump to turn: ")
            if num is not None:
                current_game = states[step].game
                idx = find_turn(states, num, current_game)
                if idx is not None:
                    step = idx


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Interactive viewer for UECda game logs"
    )
    parser.add_argument("logfile", type=Path, help="Path to game log file (JSONL)")
    args = parser.parse_args()

    if not args.logfile.exists():
        print(f"Error: File not found: {args.logfile}", file=sys.stderr)
        return 1

    print(f"Loading {args.logfile}...")
    events = load_events(args.logfile)
    print(f"Loaded {len(events)} events")

    print("Building states...")
    states = build_states(events)
    print(f"Built {len(states)} displayable states")

    if not states:
        print("Error: No states to display", file=sys.stderr)
        return 1

    print("Starting viewer...")
    curses.wrapper(lambda stdscr: main_loop(stdscr, states))
    return 0


if __name__ == "__main__":
    sys.exit(main())
