from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from itertools import combinations
from pathlib import Path
from typing import Iterable


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATE_DIR = BASE_DIR / "templates"


PLAYERS = [
    {"id": "player-1", "name": "Avi Blaze", "skill": 9},
    {"id": "player-2", "name": "Noam Steel", "skill": 8},
    {"id": "player-3", "name": "Lior Dash", "skill": 7},
    {"id": "player-4", "name": "Eitan Fox", "skill": 6},
    {"id": "player-5", "name": "Yonatan Cross", "skill": 8},
    {"id": "player-6", "name": "Matan Vale", "skill": 5},
    {"id": "player-7", "name": "Gil Storm", "skill": 7},
    {"id": "player-8", "name": "Omer Stone", "skill": 6},
    {"id": "player-9", "name": "Barak Flint", "skill": 4},
    {"id": "player-10", "name": "Roee Sparks", "skill": 9},
    {"id": "player-11", "name": "Ido Hale", "skill": 3},
    {"id": "player-12", "name": "Tal Hunter", "skill": 8},
    {"id": "player-13", "name": "Shai Wolf", "skill": 6},
    {"id": "player-14", "name": "Ariel King", "skill": 5},
    {"id": "player-15", "name": "Niv Rivers", "skill": 7},
    {"id": "player-16", "name": "Dean Knight", "skill": 4},
    {"id": "player-17", "name": "Amit Ray", "skill": 8},
    {"id": "player-18", "name": "Ben Cedar", "skill": 5},
    {"id": "player-19", "name": "Yarin Bolt", "skill": 6},
    {"id": "player-20", "name": "Gal Frost", "skill": 7},
]


@dataclass(frozen=True)
class TeamCandidate:
    teams: tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]
    averages: tuple[float, float, float]
    imbalance: float
    spread: float


def team_sizes(player_count: int) -> list[int]:
    base_size = player_count // 3
    remainder = player_count % 3
    sizes = [base_size] * 3
    for index in range(remainder):
        sizes[index] += 1
    return sorted(sizes, reverse=True)


def average_skill(team: Iterable[str], roster_lookup: dict[str, dict[str, object]]) -> float:
    members = list(team)
    return sum(int(roster_lookup[player_id]["skill"]) for player_id in members) / len(members)


def team_total_skill(team: Iterable[str], roster_lookup: dict[str, dict[str, object]]) -> int:
    members = list(team)
    return sum(int(roster_lookup[player_id]["skill"]) for player_id in members)


def canonical_teams(teams: Iterable[Iterable[str]]) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    normalized = [tuple(sorted(team)) for team in teams]
    normalized.sort(key=lambda team: (-len(team), team))
    return tuple(normalized)  # type: ignore[return-value]


def build_candidate(
    teams: tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]],
    roster_lookup: dict[str, dict[str, object]],
) -> TeamCandidate:
    averages = tuple(round(average_skill(team, roster_lookup), 2) for team in teams)
    imbalance = round(max(averages) - min(averages), 2)
    center = round(sum(averages) / 3, 4)
    spread = round(sum((average - center) ** 2 for average in averages), 4)
    return TeamCandidate(
        teams=teams,
        averages=averages,
        imbalance=imbalance,
        spread=spread,
    )


def choose_balanced_team(
    remaining_ids: list[str],
    team_size: int,
    target_skill: float,
    roster_lookup: dict[str, dict[str, object]],
    rng: random.Random,
) -> tuple[str, ...]:
    scored_teams: list[tuple[float, float, tuple[str, ...]]] = []

    for team in combinations(sorted(remaining_ids), team_size):
        total_skill = team_total_skill(team, roster_lookup)
        difference = abs(total_skill - target_skill)
        scored_teams.append((difference, rng.random(), team))

    scored_teams.sort(key=lambda item: (item[0], item[1]))

    shortlist_size = min(18, len(scored_teams))
    shortlist = scored_teams[:shortlist_size]
    bias_window = min(6, len(shortlist))

    if rng.random() < 0.82:
        return shortlist[rng.randrange(bias_window)][2]

    return shortlist[rng.randrange(len(shortlist))][2]


def build_random_candidate(
    selected_ids: list[str],
    roster_lookup: dict[str, dict[str, object]],
    rng: random.Random,
) -> TeamCandidate:
    sizes = team_sizes(len(selected_ids))
    remaining_ids = sorted(selected_ids)
    teams: list[tuple[str, ...]] = []
    remaining_team_count = len(sizes)

    for index, size in enumerate(sizes):
        if index == len(sizes) - 1:
            teams.append(tuple(sorted(remaining_ids)))
            break

        current_target = sum(int(roster_lookup[player_id]["skill"]) for player_id in remaining_ids) / remaining_team_count
        team = choose_balanced_team(remaining_ids, size, current_target, roster_lookup, rng)
        teams.append(tuple(sorted(team)))
        remaining_ids = [player_id for player_id in remaining_ids if player_id not in team]
        remaining_team_count -= 1

    return build_candidate(canonical_teams(teams), roster_lookup)


def generate_candidates(
    selected_ids: list[str],
    roster_lookup: dict[str, dict[str, object]],
) -> list[TeamCandidate]:
    rng = random.Random()
    unique_candidates: dict[tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]], TeamCandidate] = {}

    for _ in range(1400):
        candidate = build_random_candidate(selected_ids, roster_lookup, rng)
        unique_candidates[candidate.teams] = candidate

    candidates = list(unique_candidates.values())
    candidates.sort(key=lambda candidate: (candidate.imbalance, candidate.spread, candidate.teams))
    return candidates[:110]


def candidate_pair_overlap(left: TeamCandidate, right: TeamCandidate) -> tuple[int, int, int]:
    exact_repeats = 0
    heavy_overlap = 0
    total_overlap = 0

    for left_team in left.teams:
        left_set = set(left_team)
        for right_team in right.teams:
            overlap = len(left_set.intersection(right_team))
            total_overlap += overlap * overlap
            if overlap == len(left_team) == len(right_team):
                exact_repeats += 1
            elif overlap >= min(len(left_team), len(right_team)) - 1:
                heavy_overlap += 1

    return exact_repeats, heavy_overlap, total_overlap


def candidate_balance_penalty(
    candidate: TeamCandidate,
    roster_lookup: dict[str, dict[str, object]],
) -> float:
    target_team_skill = sum(int(player["skill"]) for player in roster_lookup.values()) / 3
    return round(
        sum((team_total_skill(team, roster_lookup) - target_team_skill) ** 2 for team in candidate.teams),
        4,
    )


def schedule_penalty(
    combo: tuple[TeamCandidate, ...],
    roster_lookup: dict[str, dict[str, object]],
) -> tuple[int, int, float]:
    full_team_counts: dict[tuple[str, ...], int] = {}
    teammate_pair_counts: dict[tuple[str, str], int] = {}

    for candidate in combo:
        for team in candidate.teams:
            full_team_counts[team] = full_team_counts.get(team, 0) + 1
            for pair in combinations(team, 2):
                teammate_pair_counts[pair] = teammate_pair_counts.get(pair, 0) + 1

    repeated_full_teams = sum(count - 1 for count in full_team_counts.values() if count > 1)
    repeated_teammate_pairs = sum(count - 1 for count in teammate_pair_counts.values() if count > 1)
    balance_penalty = round(
        sum(candidate_balance_penalty(candidate, roster_lookup) for candidate in combo),
        4,
    )
    return repeated_full_teams, repeated_teammate_pairs, balance_penalty


def repeated_trios_across_schedule(combo: tuple[TeamCandidate, ...]) -> int:
    trio_sets: list[set[tuple[str, str, str]]] = []

    for candidate in combo:
        candidate_trios: set[tuple[str, str, str]] = set()
        for team in candidate.teams:
            if len(team) < 3:
                continue
            for trio in combinations(team, 3):
                candidate_trios.add(tuple(sorted(trio)))
        trio_sets.append(candidate_trios)

    if not trio_sets:
        return 0

    return len(set.intersection(*trio_sets))


def schedule_score(
    combo: tuple[TeamCandidate, ...],
    roster_lookup: dict[str, dict[str, object]],
) -> tuple[int, int, int, float, float]:
    repeated_full_teams, repeated_teammate_pairs, balance_penalty = schedule_penalty(combo, roster_lookup)
    repeated_trios = repeated_trios_across_schedule(combo)
    weighted_total = round((1000 * repeated_full_teams) + (10 * repeated_teammate_pairs) + balance_penalty, 4)
    return repeated_trios, repeated_full_teams, repeated_teammate_pairs, balance_penalty, weighted_total


def choose_suggestions(
    candidates: list[TeamCandidate],
    roster_lookup: dict[str, dict[str, object]],
    limit: int = 3,
) -> list[TeamCandidate]:
    if len(candidates) <= limit:
        return candidates

    shortlist = candidates
    best_valid_combo: tuple[TeamCandidate, ...] | None = None
    best_valid_score: tuple[int, int, int, float, float] | None = None
    best_fallback_combo: tuple[TeamCandidate, ...] | None = None
    best_fallback_score: tuple[int, int, int, float, float] | None = None

    for combo in combinations(shortlist, limit):
        combo_score = schedule_score(combo, roster_lookup)

        if best_fallback_score is None or combo_score < best_fallback_score:
            best_fallback_combo = combo
            best_fallback_score = combo_score

        if combo_score[0] != 0:
            continue

        if best_valid_score is None or combo_score < best_valid_score:
            best_valid_combo = combo
            best_valid_score = combo_score

    if best_valid_combo is not None:
        return list(best_valid_combo)

    if best_fallback_combo is not None:
        return list(best_fallback_combo)

    return candidates[:limit]


def serialize_suggestion(
    candidate: TeamCandidate,
    label: str,
    roster_lookup: dict[str, dict[str, object]],
) -> dict[str, object]:
    teams = []
    for index, team in enumerate(candidate.teams, start=1):
        members = [roster_lookup[player_id] for player_id in team]
        teams.append(
            {
                "name": f"Team {index}",
                "size": len(team),
                "average_skill": round(average_skill(team, roster_lookup), 2),
                "players": members,
            }
        )

    return {
        "label": label,
        "imbalance": candidate.imbalance,
        "teams": teams,
    }


def validate_selected_players(selected_players: object) -> list[dict[str, object]]:
    if not isinstance(selected_players, list):
        raise ValueError("Expected a list of selected players.")

    validated_players: list[dict[str, object]] = []
    seen_ids: set[str] = set()

    for index, player in enumerate(selected_players, start=1):
        if not isinstance(player, dict):
            raise ValueError(f"Player {index} is invalid.")

        player_id = player.get("id")
        name = player.get("name")
        skill = player.get("skill")
        source = player.get("source", "preset")

        if not isinstance(player_id, str) or not player_id.strip():
            raise ValueError(f"Player {index} is missing an id.")
        if player_id in seen_ids:
            raise ValueError("Duplicate players were submitted.")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Player {index} is missing a name.")
        if not isinstance(skill, int) or not 1 <= skill <= 10:
            raise ValueError(f"Player {name} must have a skill between 1 and 10.")
        if source not in {"preset", "guest"}:
            raise ValueError(f"Player {name} has an invalid source.")

        seen_ids.add(player_id)
        validated_players.append(
            {
                "id": player_id,
                "name": name.strip(),
                "skill": skill,
                "source": source,
            }
        )

    if len(validated_players) < 12 or len(validated_players) > 15:
        raise ValueError("Please choose between 12 and 15 players.")

    return validated_players


def generate_suggestions(selected_players: list[dict[str, object]]) -> list[dict[str, object]]:
    roster_lookup = {str(player["id"]): player for player in selected_players}
    ordered_ids = sorted(roster_lookup)

    candidates = generate_candidates(ordered_ids, roster_lookup)
    suggestions = choose_suggestions(candidates, roster_lookup)
    suggestions.sort(key=lambda candidate: (candidate.imbalance, candidate.spread, candidate.teams))

    labels = ["Balanced Option 1", "Balanced Option 2", "Balanced Option 3"]
    return [
        serialize_suggestion(candidate, labels[index], roster_lookup)
        for index, candidate in enumerate(suggestions)
    ]


class AppHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/":
            self.serve_index()
            return

        if self.path.startswith("/static/"):
            self.serve_static()
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Page not found.")

    def do_POST(self) -> None:
        if self.path == "/api/generate":
            self.handle_generate()
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Page not found.")

    def serve_index(self) -> None:
        template = (TEMPLATE_DIR / "index.html").read_text(encoding="utf-8")
        html = template.replace("__PLAYER_DATA__", json.dumps(PLAYERS, ensure_ascii=False, separators=(",", ":")))
        body = html.encode("utf-8")

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_static(self) -> None:
        relative_path = self.path.removeprefix("/static/")
        file_path = (STATIC_DIR / relative_path).resolve()

        if not str(file_path).startswith(str(STATIC_DIR.resolve())) or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Asset not found.")
            return

        content_type = "text/plain; charset=utf-8"
        if file_path.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif file_path.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"

        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_generate(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length)
            payload = json.loads(raw_body.decode("utf-8"))
            selected_players = validate_selected_players(payload.get("selected_players", []))
            suggestions = generate_suggestions(selected_players)
            self.send_json({"suggestions": suggestions})
        except ValueError as error:
            self.send_json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)
        except json.JSONDecodeError:
            self.send_json({"error": "Invalid JSON payload."}, status=HTTPStatus.BAD_REQUEST)

    def send_json(self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"Serving football team app at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
