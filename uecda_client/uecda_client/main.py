"""Main entry point for UECda client.

Corresponds to C implementation: client.c
"""

import argparse
import logging
import sys

from uecda_client.game.state import GameState
from uecda_client.network.connection import (
    GameConnection,
    be_game_end,
    look_field,
    receive_cards,
    send_cards,
    send_changing_cards,
    start_game,
)
from uecda_client.network.protocol import TableArray
from uecda_client.strategy.analyzer import copy_table
from uecda_client.strategy.simple import SimpleStrategy

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Corresponds to C: checkArg()
    """
    parser = argparse.ArgumentParser(
        description="UECda Daifugo/Daihinmin client"
    )
    parser.add_argument(
        "-H", "--host",
        default="127.0.0.1",
        help="Server hostname or IP address (default: 127.0.0.1)"
    )
    parser.add_argument(
        "-p", "--port",
        type=int,
        default=42485,
        help="Server port number (default: 42485)"
    )
    parser.add_argument(
        "-n", "--name",
        default="PythonClient",
        help="Player name (default: PythonClient)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    return parser.parse_args()


def setup_logging(verbose: bool) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


def run_game_loop(conn: GameConnection, strategy: SimpleStrategy) -> None:
    """Run the main game loop.

    Corresponds to C: main() game loop
    """
    whole_gameend_flag = False
    game_count = 0

    while not whole_gameend_flag:
        one_gameend_flag = False

        # Start new round - receive initial cards
        own_cards_buf = start_game(conn)
        own_cards = TableArray()
        copy_table(own_cards, own_cards_buf)
        game_count += 1

        logger.info(f"Game #{game_count} started")
        logger.debug(f"Initial hand:\n{own_cards}")

        # Card exchange phase
        if own_cards_buf.get(5, 0) == 0:
            logger.error("Expected card-change turn flag")
            sys.exit(1)

        change_qty = own_cards_buf.get(5, 1)
        if 0 < change_qty < 100:
            # Need to exchange cards
            logger.info(f"Exchanging {change_qty} cards")
            select_cards = strategy.select_exchange(own_cards, change_qty)
            send_changing_cards(conn, select_cards)
            logger.debug(f"Sent exchange cards:\n{select_cards}")
        else:
            # No exchange needed (heimin)
            logger.debug("No card exchange needed")

        # Main turn loop
        while not one_gameend_flag:
            # Receive card info and check if it's our turn
            own_cards_buf, is_my_turn = receive_cards(conn)
            copy_table(own_cards, own_cards_buf)

            if is_my_turn:
                # Parse game state
                state = GameState.from_table(own_cards_buf, own_cards)

                logger.debug(
                    f"My turn - onset={state.onset}, rev={state.rev}, "
                    f"lock={state.lock}, ord={state.ord}, qty={state.qty}"
                )

                # Select cards to play
                select_cards = strategy.select_play(own_cards, state)

                # Send selected cards
                accept_flag = send_cards(conn, select_cards)
                if accept_flag == 1:
                    logger.debug("Cards accepted")
                elif accept_flag in (8, 9):
                    # 8/9 = pass or not my turn (normal)
                    logger.debug(f"Pass or field cleared (flag={accept_flag})")
                else:
                    logger.warning(f"Unexpected accept flag: {accept_flag}")

            # Receive field state after play (required by protocol)
            look_field(conn)

            # Check game end
            end_status = be_game_end(conn)
            if end_status == 0:
                # Game continues
                pass
            elif end_status == 1:
                # One game ended
                one_gameend_flag = True
                logger.info(f"Game #{game_count} finished")
            else:
                # All games ended
                one_gameend_flag = True
                whole_gameend_flag = True
                logger.info(f"All games finished (Total: {game_count} games)")


def main() -> None:
    """Main entry point."""
    args = parse_args()
    setup_logging(args.verbose)

    logger.info(f"Connecting to {args.host}:{args.port} as '{args.name}'")

    strategy = SimpleStrategy()

    try:
        with GameConnection(args.host, args.port) as conn:
            player_id = conn.send_profile(args.name)
            logger.info(f"Joined game as player {player_id}")

            run_game_loop(conn, strategy)

    except ConnectionRefusedError:
        logger.error(f"Could not connect to server at {args.host}:{args.port}")
        sys.exit(1)
    except ConnectionError as e:
        logger.error(f"Connection error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)

    logger.info("Client finished")


if __name__ == "__main__":
    main()
