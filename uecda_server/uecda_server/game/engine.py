"""Game engine for UECda."""

from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING, Callable

from uecda_server.config import Config
from uecda_server.logging import GameLogger
from uecda_server.models.card import CardSet, Rank, create_full_deck
from uecda_server.models.game_state import CardType, GameState
from uecda_server.models.player import Player, PlayerRank
from uecda_server.network.protocol import TableArray
from uecda_server.network.server import GameServer

from .analyzer import CardAnalyzer
from .validator import MoveValidator

if TYPE_CHECKING:
    from .analyzer import CardAnalysis

logger = logging.getLogger(__name__)

# Special ranks (column indices in protocol)
RANK_EIGHT = Rank.EIGHT  # 8切り
RANK_THREE = Rank.THREE  # スペ3
RANK_ELEVEN = Rank.JACK  # 11バック (J=11)

# Pass threshold for sennichite
SENNICHITE_THRESHOLD = 20


class GameEngine:
    """Main game engine for UECda."""

    def __init__(
        self,
        server: GameServer,
        config: Config | None = None,
        game_logger: GameLogger | None = None,
    ):
        """Initialize game engine.

        Args:
            server: GameServer instance
            config: Configuration (uses defaults if not provided)
            game_logger: GameLogger instance for detailed logging
        """
        self.server = server
        self.config = config or Config()
        self.rules = self.config.rules
        self.game_logger = game_logger

        self.analyzer = CardAnalyzer()
        self.validator = MoveValidator(self.analyzer)

        self.state = GameState()
        self.hands: list[CardSet] = []
        self.seat_order: list[int] = []  # Player IDs in seat order

        self._on_turn: Callable[[int, str], None] | None = None
        self._on_game_end: Callable[[int, list[int]], None] | None = None

    @property
    def players(self) -> list[Player]:
        """Get players from server."""
        return self.server.players

    def set_callbacks(
        self,
        on_turn: Callable[[int, str], None] | None = None,
        on_game_end: Callable[[int, list[int]], None] | None = None,
    ) -> None:
        """Set event callbacks.

        Args:
            on_turn: Called on each turn (turn_number, description)
            on_game_end: Called when game ends (game_number, finish_order)
        """
        self._on_turn = on_turn
        self._on_game_end = on_game_end

    def run_games(self, num_games: int | None = None) -> dict[int, int]:
        """Run multiple games.

        Args:
            num_games: Number of games (uses config if not specified)

        Returns:
            Dict of player_id -> total points
        """
        num_games = num_games or self.config.game.num_games
        self._total_games = num_games  # Store for use in run_game
        points: dict[int, int] = {p.player_id: 0 for p in self.players}

        # Log session start
        if self.game_logger:
            self.game_logger.log_session_start(self.players)

        for game_num in range(1, num_games + 1):
            self.state.game_number = game_num
            logger.info(f"Starting game {game_num}/{num_games}")

            # Run single game (game end signal is sent inside run_game)
            finish_order = self.run_game()

            # Award points (5 for 1st, 4 for 2nd, etc.)
            for rank, player_id in enumerate(finish_order):
                points[player_id] += 5 - rank

            # Update player ranks for next game
            for rank, player_id in enumerate(finish_order):
                self.players[player_id].rank = PlayerRank(rank)

        # Log session end
        if self.game_logger:
            # Calculate ranking from final points
            ranking = sorted(points.keys(), key=lambda p: points[p], reverse=True)
            self.game_logger.log_session_end(num_games, points, ranking)

        return points

    def run_game(self) -> list[int]:
        """Run a single game.

        Returns:
            List of player IDs in finish order (0=1st place)
        """
        # Initialize game
        self._init_game()

        # Log game start (before exchange, with initial hands)
        if self.game_logger:
            self.game_logger.log_game_start(
                self.state.game_number,
                self.hands,
                self.players,
                self.state.current_player,
            )

        # Card exchange phase - always send initial hand info
        self._send_initial_hands()
        if self.rules.card_exchange and self.state.game_number > 1:
            self._do_card_exchange()

        # Main game loop
        finish_order: list[int] = []

        game_ended = False
        while self.state.finished_count < 4 and not game_ended:
            self.state.turn_number += 1

            # Get current player
            current = self.state.current_player
            player = self.players[current]

            # Skip finished players
            if player.has_finished:
                self._advance_player()
                continue

            # Skip passed players (if not a new round)
            if player.has_passed and not self.state.field.is_empty():
                self._advance_player()
                continue

            # Send hand info to all players
            self._send_all_hand_info()

            # Get move from current player
            submitted_cards, joker_positions = self._get_player_move(player)

            # Analyze and validate
            analysis = self.analyzer.analyze(
                submitted_cards,
                joker_positions,
                self.state.effective_revolution(),
            )

            validation = self.validator.validate(
                analysis,
                self.hands[current],
                submitted_cards,
                self.state,
                joker_positions,
            )

            # Process move
            if validation.is_valid and not validation.is_pass:
                self._process_valid_move(player, submitted_cards, analysis, joker_positions)
                self.server.send_accept(player)

                # Log turn (play)
                if self.game_logger:
                    self.game_logger.log_turn(
                        self.state.game_number,
                        self.state.turn_number,
                        current,
                        "play",
                        submitted_cards,
                        analysis.card_type,
                        self.state.field.cards,
                        self.hands,
                        self.state,
                    )

                # Check for finish
                if self.hands[current].count() == 0:
                    player.has_finished = True
                    player.finish_order = self.state.finished_count
                    finish_order.append(current)
                    self.state.finished_count += 1
                    logger.info(f"Player {current} finished in position {len(finish_order)}")

                    # Log player finish
                    if self.game_logger:
                        self.game_logger.log_special(
                            self.state.game_number,
                            self.state.turn_number,
                            "player_finish",
                            current,
                            {"position": len(finish_order)},
                        )
            else:
                # Pass
                player.has_passed = True
                self.state.consecutive_passes += 1
                self.server.send_reject(player)

                # Log turn (pass)
                if self.game_logger:
                    self.game_logger.log_turn(
                        self.state.game_number,
                        self.state.turn_number,
                        current,
                        "pass",
                        CardSet(),  # Empty cards for pass
                        CardType.EMPTY,
                        self.state.field.cards,
                        self.hands,
                        self.state,
                    )

            # Send field info to all players
            self._send_all_field_info()

            # Check for round end (all passed)
            if self._check_all_passed():
                self._clear_field()

                # Log field clear
                if self.game_logger:
                    self.game_logger.log_special(
                        self.state.game_number,
                        self.state.turn_number,
                        "field_clear",
                        self.state.current_player,
                        {"reason": "all_passed"},
                    )

            # Check for sennichite
            if self.state.consecutive_passes >= SENNICHITE_THRESHOLD:
                logger.warning("Sennichite! Resolving remaining positions randomly.")
                finish_order = self._resolve_sennichite(finish_order)
                game_ended = True
                # Send game end signal (handled below)

            # Check if game ended (4 players finished)
            if self.state.finished_count >= 4:
                game_ended = True
                # Send game end signal
                all_done = self.state.game_number == getattr(self, "_total_games", 1)
                for p in self.players:
                    self.server.send_game_end(p, all_games_end=all_done)

            if not game_ended:
                # Send continue signal
                for p in self.players:
                    self.server.send_game_continue(p)

                # Advance to next player
                self._advance_player()

        # Handle last remaining player
        if self.state.finished_count == 4:
            for p in self.players:
                if not p.has_finished:
                    p.has_finished = True
                    p.finish_order = 4
                    finish_order.append(p.player_id)
                    break

        # For sennichite, also send game end
        if self.state.consecutive_passes >= SENNICHITE_THRESHOLD:
            all_done = self.state.game_number == getattr(self, "_total_games", 1)
            for p in self.players:
                self.server.send_game_end(p, all_games_end=all_done)

        # Log game end
        if self.game_logger:
            self.game_logger.log_game_end(
                self.state.game_number,
                finish_order,
                self.players,
            )

        if self._on_game_end:
            self._on_game_end(self.state.game_number, finish_order)

        return finish_order

    def _init_game(self) -> None:
        """Initialize state for a new game."""
        self.state.reset_for_new_game()

        # Reset players
        for player in self.players:
            player.reset_game_state()

        # Initialize seat order
        self.seat_order = list(range(len(self.players)))

        # Shuffle and deal cards
        self._deal_cards()

        # First player is daifugo (or player 0 in first game)
        if self.state.game_number == 1:
            self.state.current_player = 0
        else:
            # Find daifugo
            for player in self.players:
                if player.rank == PlayerRank.DAIFUGO:
                    self.state.current_player = player.player_id
                    break

        logger.info(
            f"Game {self.state.game_number} initialized, first player: {self.state.current_player}"
        )

    def _deal_cards(self) -> None:
        """Shuffle and deal cards to all players.

        Matches C implementation:
        - First game: random player as starting point, deal in seat order
        - Subsequent games: daifugo as starting point, deal in seat order
        """
        deck = create_full_deck()
        cards = deck.to_list()
        random.shuffle(cards)

        # Initialize hands
        self.hands = [CardSet() for _ in range(len(self.players))]

        # Determine starting player for card distribution
        # C impl: shuffle_card(initial_person, ..., sekijun)
        # initial_person is random for first game, mibun[0] (daifugo) for others
        if self.state.game_number == 1:
            # First game: random starting position
            initial_player = random.randint(0, len(self.players) - 1)
        else:
            # Subsequent games: start from daifugo
            initial_player = -1
            for player in self.players:
                if player.rank == PlayerRank.DAIFUGO:
                    initial_player = player.player_id
                    break
            if initial_player < 0:
                initial_player = 0  # fallback

        # Get seat position of initial player
        initial_seat = self.seat_order.index(initial_player)

        # Deal cards round-robin starting from initial_seat in seat order
        num_players = len(self.players)
        for i, card in enumerate(cards):
            seat_idx = (i + initial_seat) % num_players
            player_id = self.seat_order[seat_idx]
            self.hands[player_id].add(card)

        logger.debug(
            f"Cards dealt to all players (starting from player {initial_player})"
        )

    def _send_initial_hands(self) -> None:
        """Send initial hand info to all players at start of game.

        This is required before the card exchange phase.
        [5][0] = 1 indicates this is the initial hand phase.
        [5][1] = exchange count:
            - 大富豪: 2 (gives 2 to 大貧民, receives 2 strongest)
            - 富豪: 1 (gives 1 to 貧民, receives 1 strongest)
            - 平民: 0 (no exchange)
            - 貧民: -1 (gives 1 strongest, receives 1)
            - 大貧民: -2 (gives 2 strongest, receives 2)

        For 貧民/大貧民, the server auto-extracts strongest cards before sending.
        """
        is_exchange_game = self.rules.card_exchange and self.state.game_number > 1

        # Find players by rank for exchange
        players_by_rank: dict[PlayerRank, Player] = {}
        for p in self.players:
            players_by_rank[p.rank] = p

        # For exchange games, pre-extract strongest cards from 貧民/大貧民
        extracted_cards: dict[int, CardSet] = {}  # player_id -> cards
        pre_exchange_hands: dict[int, CardSet] = {}  # For 貧民/大貧民

        if is_exchange_game:
            # 大貧民 gives 2 strongest to 大富豪
            if PlayerRank.DAIHINMIN in players_by_rank:
                daihinmin = players_by_rank[PlayerRank.DAIHINMIN]
                pre_exchange_hands[daihinmin.player_id] = self.hands[
                    daihinmin.player_id
                ].copy()
                extracted = self._extract_strongest(daihinmin.player_id, 2)
                extracted_cards[daihinmin.player_id] = extracted
                # Transfer to 大富豪's hand
                daifugo = players_by_rank[PlayerRank.DAIFUGO]
                for card in extracted:
                    self.hands[daifugo.player_id].add(card)

            # 貧民 gives 1 strongest to 富豪
            if PlayerRank.HINMIN in players_by_rank:
                hinmin = players_by_rank[PlayerRank.HINMIN]
                pre_exchange_hands[hinmin.player_id] = self.hands[
                    hinmin.player_id
                ].copy()
                extracted = self._extract_strongest(hinmin.player_id, 1)
                extracted_cards[hinmin.player_id] = extracted
                # Transfer to 富豪's hand
                fugo = players_by_rank[PlayerRank.FUGO]
                for card in extracted:
                    self.hands[fugo.player_id].add(card)

        # Send hands to all players
        # For exchange games (game 2+), send IN RANK ORDER (matching C implementation)
        # Order: 大富豪, 富豪, 平民, 貧民, 大貧民
        if is_exchange_game:
            rank_order = [
                PlayerRank.DAIFUGO,
                PlayerRank.FUGO,
                PlayerRank.HEIMIN,
                PlayerRank.HINMIN,
                PlayerRank.DAIHINMIN,
            ]
            players_to_send = [players_by_rank[r] for r in rank_order if r in players_by_rank]
        else:
            # First game: send in player ID order
            players_to_send = list(self.players)

        for player in players_to_send:
            # Calculate exchange count based on rank
            if is_exchange_game:
                if player.rank == PlayerRank.DAIFUGO:
                    exchange_count = 2
                elif player.rank == PlayerRank.FUGO:
                    exchange_count = 1
                elif player.rank == PlayerRank.HINMIN:
                    exchange_count = -1  # Negative = gives strongest
                elif player.rank == PlayerRank.DAIHINMIN:
                    exchange_count = -2  # Negative = gives strongest
                else:
                    exchange_count = 0
            else:
                exchange_count = 0

            table = TableArray()

            # 貧民/大貧民 receive their pre-exchange hand (before strongest taken)
            if player.player_id in pre_exchange_hands:
                table.set_cards(pre_exchange_hands[player.player_id])
            else:
                table.set_cards(self.hands[player.player_id])

            table.set_game_state(
                self.state,
                self.players,
                self.hands,
                player.player_id,
                is_exchange_phase=True,  # [5][0] = 1
                exchange_count=exchange_count,  # [5][1]
            )
            self.server.send_table(player, table)

        logger.debug("Initial hands sent to all players")

    def _extract_strongest(self, player_id: int, count: int) -> CardSet:
        """Extract strongest cards from player's hand.

        Args:
            player_id: Player ID
            count: Number of cards to extract

        Returns:
            CardSet of extracted cards (also removes from hand)
        """
        hand = self.hands[player_id]
        hand_sorted = sorted(
            hand.to_list(),
            key=lambda c: c.strength(),
            reverse=True,
        )

        extracted = CardSet()
        for card in hand_sorted[:count]:
            extracted.add(card)
            hand.remove(card)

        return extracted

    def _do_card_exchange(self) -> None:
        """Perform card exchange between ranks.

        The exchange flow (matching C implementation):
        1. 貧民/大貧民's strongest cards already extracted in _send_initial_hands
        2. Receive cards from 大富豪 (2 cards) -> give to 大貧民
        3. Receive cards from 富豪 (1 card) -> give to 貧民
        """
        # Find players by rank
        players_by_rank: dict[PlayerRank, Player] = {}
        for p in self.players:
            players_by_rank[p.rank] = p
            logger.debug(f"Player {p.player_id} ({p.name}) has rank {p.rank}")

        # Track exchanges for logging
        exchanges: list[dict] = []

        # Exchange 1: 大富豪 -> 大貧民 (2 cards)
        if PlayerRank.DAIFUGO in players_by_rank and PlayerRank.DAIHINMIN in players_by_rank:
            daifugo = players_by_rank[PlayerRank.DAIFUGO]
            daihinmin = players_by_rank[PlayerRank.DAIHINMIN]

            logger.debug(f"Waiting for exchange cards from 大富豪 (Player {daifugo.player_id})")

            # Get cards from 大富豪
            daifugo_cards = self._get_exchange_cards_from_high(daifugo, 2)

            # Transfer to 大貧民
            for card in daifugo_cards:
                self.hands[daifugo.player_id].remove(card)
                self.hands[daihinmin.player_id].add(card)

            # Record exchange for logging
            exchanges.append({
                "from": daifugo.player_id,
                "to": daihinmin.player_id,
                "cards": daifugo_cards,
            })

            logger.info(
                f"Exchange: Player {daifugo.player_id} gave 2 cards to "
                f"Player {daihinmin.player_id}"
            )
        else:
            logger.warning("Could not find DAIFUGO or DAIHINMIN for exchange")

        # Exchange 2: 富豪 -> 貧民 (1 card)
        if PlayerRank.FUGO in players_by_rank and PlayerRank.HINMIN in players_by_rank:
            fugo = players_by_rank[PlayerRank.FUGO]
            hinmin = players_by_rank[PlayerRank.HINMIN]

            logger.debug(f"Waiting for exchange cards from 富豪 (Player {fugo.player_id})")

            # Get cards from 富豪
            fugo_cards = self._get_exchange_cards_from_high(fugo, 1)

            # Transfer to 貧民
            for card in fugo_cards:
                self.hands[fugo.player_id].remove(card)
                self.hands[hinmin.player_id].add(card)

            # Record exchange for logging
            exchanges.append({
                "from": fugo.player_id,
                "to": hinmin.player_id,
                "cards": fugo_cards,
            })

            logger.info(
                f"Exchange: Player {fugo.player_id} gave 1 card to "
                f"Player {hinmin.player_id}"
            )
        else:
            logger.warning("Could not find FUGO or HINMIN for exchange")

        # Log all exchanges
        if self.game_logger and exchanges:
            self.game_logger.log_exchange(
                self.state.game_number,
                exchanges,
                self.hands,
            )

    def _get_exchange_cards_from_high(
        self,
        player: Player,
        count: int,
    ) -> CardSet:
        """Get cards selected for exchange from high rank player.

        Args:
            player: 大富豪 or 富豪
            count: Number of cards to receive

        Returns:
            CardSet of selected cards
        """
        table = self.server.recv_table(player)
        cards, _ = table.get_submitted_cards()

        # Validate count
        if cards.count() != count:
            logger.warning(
                f"Invalid exchange from player {player.player_id}: "
                f"expected {count}, got {cards.count()}. Auto-selecting."
            )
            # Auto-select weakest cards (high rank can give any)
            hand_sorted = sorted(
                self.hands[player.player_id].to_list(),
                key=lambda c: c.strength(),
                reverse=False,  # Weakest first
            )
            cards = CardSet()
            for card in hand_sorted[:count]:
                cards.add(card)

        # Check all cards are in hand
        for card in cards:
            if card not in self.hands[player.player_id]:
                logger.warning(
                    f"Player {player.player_id} submitted card not in hand. Auto-selecting."
                )
                hand_sorted = sorted(
                    self.hands[player.player_id].to_list(),
                    key=lambda c: c.strength(),
                    reverse=False,
                )
                cards = CardSet()
                for c in hand_sorted[:count]:
                    cards.add(c)
                break

        return cards

    def _send_all_hand_info(self) -> None:
        """Send hand info to all players."""
        for player in self.players:
            table = TableArray()
            table.set_cards(self.hands[player.player_id])
            table.set_game_state(
                self.state,
                self.players,
                self.hands,
                player.player_id,
            )
            self.server.send_table(player, table)

    def _send_all_field_info(self) -> None:
        """Send field info to all players."""
        for player in self.players:
            table = TableArray()
            table.set_cards(self.state.field.cards)
            self.server.send_table(player, table)

    def _get_player_move(self, player: Player) -> tuple[CardSet, dict]:
        """Get move from player.

        Returns:
            Tuple of (cards, joker_positions)
        """
        table = self.server.recv_table(player)
        return table.get_submitted_cards()

    def _process_valid_move(
        self,
        player: Player,
        cards: CardSet,
        analysis: "CardAnalysis",
        joker_positions: dict,
    ) -> None:
        """Process a valid move."""
        pid = player.player_id
        field = self.state.field

        # Remove cards from hand
        for card in cards:
            if card.is_joker:
                # Remove actual joker from hand
                joker = self.hands[pid].get_joker()
                if joker:
                    self.hands[pid].remove(joker)
            elif (card.suit, card.rank) in joker_positions:
                # Joker was used as substitute - remove joker
                joker = self.hands[pid].get_joker()
                if joker:
                    self.hands[pid].remove(joker)
            else:
                self.hands[pid].remove(card)

        # Update field
        field.cards = cards.copy()
        field.card_type = analysis.card_type
        field.card_count = analysis.count
        field.base_rank = analysis.base_rank
        field.suit_pattern = analysis.suit_pattern

        # Update game state
        self.state.last_player = pid
        self.state.consecutive_passes = 0

        # Check for special rules
        self._apply_special_rules(analysis)

        # Update lock (shibari)
        self._update_lock(analysis)

        logger.debug(f"Player {pid} played: {cards}")

    def _apply_special_rules(self, analysis: CardAnalysis) -> None:
        """Apply special rules based on played cards."""
        revolution = self.state.effective_revolution()

        # Joker single
        if analysis.card_type == CardType.JOKER_SINGLE:
            self.state.is_joker_single = True
        else:
            self.state.is_joker_single = False

        # 8切り (Eight Stop)
        if self.rules.eight_stop:
            if self.analyzer.check_special_card(analysis, RANK_EIGHT, revolution):
                logger.info("8切り! Field cleared.")

                # Log eight stop
                if self.game_logger:
                    self.game_logger.log_special(
                        self.state.game_number,
                        self.state.turn_number,
                        "eight_stop",
                        self.state.last_player,
                    )

                self._clear_field()

        # 革命 (Revolution)
        if self.rules.revolution:
            is_revolution_play = False
            if analysis.card_type == CardType.PAIR and analysis.count >= 4:
                is_revolution_play = True
            elif analysis.card_type == CardType.SEQUENCE and analysis.count >= 5:
                is_revolution_play = True

            if is_revolution_play:
                self.state.is_revolution = not self.state.is_revolution
                rev_status = "ON" if self.state.is_revolution else "OFF"
                logger.info(f"革命! Revolution is now {rev_status}")

                # Log revolution
                if self.game_logger:
                    self.game_logger.log_special(
                        self.state.game_number,
                        self.state.turn_number,
                        "revolution",
                        self.state.last_player,
                        {"is_revolution": self.state.is_revolution},
                    )

        # 11バック (Eleven Back)
        if self.rules.eleven_back:
            if self.analyzer.check_special_card(analysis, RANK_ELEVEN, revolution):
                self.state.is_eleven_back = not self.state.is_eleven_back
                back_status = "ON" if self.state.is_eleven_back else "OFF"
                logger.info(f"11バック! Eleven back is now {back_status}")

                # Log eleven back
                if self.game_logger:
                    self.game_logger.log_special(
                        self.state.game_number,
                        self.state.turn_number,
                        "eleven_back",
                        self.state.last_player,
                        {"is_eleven_back": self.state.is_eleven_back},
                    )

    def _update_lock(self, analysis: CardAnalysis) -> None:
        """Update lock (shibari) state."""
        if not self.rules.lock:
            return

        field = self.state.field

        if field.is_empty():
            field.is_locked = False
            field.lock_count = 0
        elif analysis.suit_pattern == field.suit_pattern:
            field.lock_count += 1
            if field.lock_count >= 2 and not field.is_locked:
                field.is_locked = True
                logger.info("縛り! Lock activated.")

                # Log lock activation
                if self.game_logger:
                    self.game_logger.log_special(
                        self.state.game_number,
                        self.state.turn_number,
                        "lock",
                        self.state.last_player,
                    )
        else:
            field.lock_count = 1
            field.is_locked = False

    def _check_all_passed(self) -> bool:
        """Check if all active players have passed."""
        active_players = [p for p in self.players if not p.has_finished]
        passed_count = sum(1 for p in active_players if p.has_passed)
        return passed_count >= len(active_players) - 1  # All except last player

    def _clear_field(self) -> None:
        """Clear the field (場が流れる)."""
        self.state.reset_for_new_round()

        # Reset pass flags
        for player in self.players:
            player.reset_turn_state()

        # Next player is last one who played
        if self.state.last_player >= 0:
            self.state.current_player = self.state.last_player

        logger.debug("Field cleared")

    def _advance_player(self) -> None:
        """Advance to next player."""
        # Simple round-robin for now
        num_players = len(self.players)
        direction = self.state.direction

        next_player = (self.state.current_player + direction) % num_players

        # Skip finished players
        attempts = 0
        while self.players[next_player].has_finished and attempts < num_players:
            next_player = (next_player + direction) % num_players
            attempts += 1

        self.state.current_player = next_player

    def _resolve_sennichite(self, current_order: list[int]) -> list[int]:
        """Resolve sennichite by randomly assigning remaining positions.

        Args:
            current_order: Current finish order

        Returns:
            Complete finish order
        """
        remaining = [
            p.player_id
            for p in self.players
            if p.player_id not in current_order
        ]
        random.shuffle(remaining)

        for pid in remaining:
            current_order.append(pid)
            self.players[pid].has_finished = True
            self.players[pid].finish_order = len(current_order) - 1

        return current_order
