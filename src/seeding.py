from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil


@dataclass
class PlayerStanding:
    entrant_id: int
    name: str
    pool_id: int
    pool_name: str
    placement: int
    match_wins: int = 0
    match_losses: int = 0
    points_for: int = 0
    points_against: int = 0
    sets_played: int = 0

    @property
    def match_winrate(self) -> float:
        total = self.match_wins + self.match_losses
        return self.match_wins / total if total else 0.0

    @property
    def point_winrate(self) -> float:
        total = self.points_for + self.points_against
        return self.points_for / total if total else 0.0

    @property
    def point_differential_per_set(self) -> float:
        if not self.sets_played:
            return 0.0
        return (self.points_for - self.points_against) / self.sets_played

    @property
    def points_for_per_set(self) -> float:
        return self.points_for / self.sets_played if self.sets_played else 0.0

    def ranking_key(self) -> tuple:
        return (
            self.placement,
            -self.match_winrate,
            -self.point_winrate,
            -self.point_differential_per_set,
            -self.points_for_per_set,
            -self.points_for,
            self.name.casefold(),
            self.entrant_id,
        )

    def competitive_key(self) -> tuple:
        return self.ranking_key()[:-2]


@dataclass
class SeedAdjustment:
    first_seed: int
    first_name: str
    second_seed: int
    second_name: str
    pool_name: str


@dataclass
class BracketSeeding:
    name: str
    players: list[PlayerStanding]
    adjustments: list[SeedAdjustment] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def build_player_standings(
    pool_id: int,
    pool_name: str,
    standings: list[dict],
    sets: list[dict],
) -> list[PlayerStanding]:
    players = {}
    for standing in standings:
        entrant = standing.get("entrant") or {}
        entrant_id = entrant.get("id")
        placement = standing.get("placement")
        if entrant_id is None or placement is None:
            continue

        players[int(entrant_id)] = PlayerStanding(
            entrant_id=int(entrant_id),
            name=entrant.get("name") or f"Entrant {entrant_id}",
            pool_id=pool_id,
            pool_name=pool_name,
            placement=int(placement),
        )

    for set_data in sets:
        if str(set_data.get("state")).casefold() not in {"3", "completed"}:
            continue

        slots = [slot for slot in set_data.get("slots") or [] if slot.get("entrant")]
        if len(slots) != 2:
            continue

        winner_id = set_data.get("winnerId")
        for slot in slots:
            entrant = slot["entrant"]
            entrant_id = int(entrant["id"])
            player = players.get(entrant_id)
            if player is None:
                continue

            opponent_slot = slots[0] if slots[1] == slot else slots[1]
            score = normalize_score(get_slot_score(slot))
            opponent_score = normalize_score(get_slot_score(opponent_slot))
            player.points_for += score
            player.points_against += opponent_score
            player.sets_played += 1
            if str(winner_id) == str(entrant_id):
                player.match_wins += 1
            else:
                player.match_losses += 1

    return list(players.values())


def rank_players(players: list[PlayerStanding]) -> tuple[list[PlayerStanding], list[str]]:
    ranked = sorted(players, key=lambda player: player.ranking_key())
    warnings = []
    for first, second in zip(ranked, ranked[1:]):
        if first.competitive_key() == second.competitive_key():
            warnings.append(
                f"Manual review: {first.name} and {second.name} remain tied after every tiebreaker."
            )
    return ranked, warnings


def split_into_brackets(ranked: list[PlayerStanding]) -> list[BracketSeeding]:
    sizes = get_bracket_sizes(len(ranked))
    brackets = []
    start = 0
    for name, size in sizes:
        players = list(ranked[start:start + size])
        start += size
        seeded, adjustments, warnings = avoid_first_round_rematches(players)
        brackets.append(
            BracketSeeding(
                name=name,
                players=seeded,
                adjustments=adjustments,
                warnings=warnings,
            )
        )
    return brackets


def get_bracket_sizes(player_count: int) -> list[tuple[str, int]]:
    if player_count <= 0:
        return []
    if player_count <= 7:
        return [("Final", player_count)]
    if player_count <= 17:
        return [
            ("Principal", ceil(player_count / 2)),
            ("Secundario", player_count // 2),
        ]
    if player_count <= 23:
        base, remainder = divmod(player_count, 3)
        return [
            ("Principal", base + (1 if remainder == 2 else 0)),
            ("Intermedio", base),
            ("Principiante", base + (1 if remainder >= 1 else 0)),
        ]

    base, remainder = divmod(player_count, 4)
    return [
        ("Maestro", base + (1 if remainder >= 1 else 0)),
        ("Avanzado", base + (1 if remainder >= 2 else 0)),
        ("Intermedio", base + (1 if remainder >= 3 else 0)),
        ("Principiante", base),
    ]


def avoid_first_round_rematches(
    players: list[PlayerStanding],
    max_seed_shift: int = 2,
) -> tuple[list[PlayerStanding], list[SeedAdjustment], list[str]]:
    seeded = list(players)
    adjustments = []
    while True:
        rematches = get_first_round_rematches(seeded)
        if not rematches:
            break

        current_count = len(rematches)
        best_swap = None
        best_count = current_count
        for first_seed, second_seed in rematches:
            for target_seed in (first_seed, second_seed):
                target_index = target_seed - 1
                for candidate_index in range(len(seeded)):
                    if candidate_index == target_index:
                        continue
                    if abs(candidate_index - target_index) > max_seed_shift:
                        continue

                    candidate = list(seeded)
                    candidate[target_index], candidate[candidate_index] = (
                        candidate[candidate_index],
                        candidate[target_index],
                    )
                    candidate_count = len(get_first_round_rematches(candidate))
                    if candidate_count < best_count:
                        best_count = candidate_count
                        best_swap = (target_index, candidate_index)

        if best_swap is None:
            break

        first_index, second_index = best_swap
        first_player = seeded[first_index]
        second_player = seeded[second_index]
        seeded[first_index], seeded[second_index] = second_player, first_player
        adjustments.append(
            SeedAdjustment(
                first_seed=first_index + 1,
                first_name=first_player.name,
                second_seed=second_index + 1,
                second_name=second_player.name,
                pool_name=first_player.pool_name,
            )
        )

    warnings = []
    for first_seed, second_seed in get_first_round_rematches(seeded):
        first = seeded[first_seed - 1]
        second = seeded[second_seed - 1]
        warnings.append(
            f"Could not avoid {first.name} vs {second.name} from {first.pool_name} in Winners R1."
        )

    return seeded, adjustments, warnings


def get_first_round_rematches(players: list[PlayerStanding]) -> list[tuple[int, int]]:
    rematches = []
    for first_seed, second_seed in get_first_round_pairings(len(players)):
        first = players[first_seed - 1]
        second = players[second_seed - 1]
        if first.pool_id == second.pool_id:
            rematches.append((first_seed, second_seed))
    return rematches


def get_first_round_pairings(player_count: int) -> list[tuple[int, int]]:
    if player_count < 2:
        return []

    bracket_size = 1
    while bracket_size < player_count:
        bracket_size *= 2

    seed_order = [1, 2]
    current_size = 2
    while current_size < bracket_size:
        next_size = current_size * 2
        expanded = []
        for seed in seed_order:
            expanded.extend((seed, next_size + 1 - seed))
        seed_order = expanded
        current_size = next_size

    pairings = []
    for index in range(0, len(seed_order), 2):
        first_seed = seed_order[index]
        second_seed = seed_order[index + 1]
        if first_seed <= player_count and second_seed <= player_count:
            pairings.append((first_seed, second_seed))
    return pairings


def get_slot_score(slot: dict) -> int | float | None:
    standing = slot.get("standing") or {}
    stats = standing.get("stats") or {}
    score = stats.get("score") or {}
    return score.get("value")


def normalize_score(score: int | float | None) -> int:
    if score is None or score < 0:
        return 0
    return int(score)
