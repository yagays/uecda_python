"""Main entry point for UECda server."""

import argparse
import logging
import sys
from pathlib import Path

from uecda_server.config import load_config
from uecda_server.game.engine import GameEngine
from uecda_server.logging import GameLogConfig, GameLogger
from uecda_server.network.server import GameServer
from uecda_server.utils.logger import GameDisplay, setup_logging

logger = logging.getLogger(__name__)


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success)
    """
    parser = argparse.ArgumentParser(
        description="UECda Daifugo/Daihinmin card game server"
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        help="Path to config file (YAML)",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        help="Server port (overrides config)",
    )
    parser.add_argument(
        "-n",
        "--num-games",
        type=int,
        help="Number of games to play (overrides config)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--show-hands",
        action="store_true",
        help="Show player hands in output",
    )
    parser.add_argument(
        "--game-log",
        type=Path,
        help="Path to game log file (JSONL format)",
    )

    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    # Apply command-line overrides
    if args.port:
        config.server.port = args.port
    if args.num_games:
        config.game.num_games = args.num_games
    if args.verbose:
        config.logging.level = "DEBUG"
    if args.show_hands:
        config.logging.show_hands = True

    # Setup game log config (CLI argument overrides config file)
    game_log_config = GameLogConfig(
        enabled=args.game_log is not None or config.game_log.enabled,
        output_path=str(args.game_log) if args.game_log else config.game_log.output_path,
    )

    # Setup logging
    setup_logging(config.logging.level)

    # Create display
    display = GameDisplay(show_hands=config.logging.show_hands)

    print("UECda Server starting...")
    print(f"Port: {config.server.port}")
    print(f"Games: {config.game.num_games}")
    print(f"Players: {config.game.num_players}")
    if game_log_config.enabled:
        print(f"Game log: {game_log_config.output_path}")
    print()

    # Create and start server
    try:
        with GameServer(
            host=config.server.host,
            port=config.server.port,
            num_players=config.game.num_players,
        ) as server:
            # Wait for players
            print(f"Waiting for {config.game.num_players} players to connect...")
            players = server.accept_players(
                on_connect=display.print_player_connected
            )
            display.print_all_connected(players)

            # Create game logger
            with GameLogger(game_log_config) as game_logger:
                # Create game engine
                engine = GameEngine(server, config, game_logger)

                # Set up display callbacks
                def on_game_end(game_num: int, finish_order: list[int]) -> None:
                    display.print_game_end(game_num, finish_order, players)

                engine.set_callbacks(on_game_end=on_game_end)

                # Run games
                print(f"Starting {config.game.num_games} games...")
                display.print_separator()

                points = engine.run_games()

                # Print final results
                display.print_final_results(points, players)

            return 0

    except KeyboardInterrupt:
        print("\nServer interrupted by user")
        return 1
    except Exception as e:
        logger.exception(f"Server error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
