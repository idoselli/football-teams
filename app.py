from __future__ import annotations

import csv
import json
import os
import random
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Iterable

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import BadRequest


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATE_DIR = BASE_DIR / "templates"
RATINGS_CSV = BASE_DIR / "ratings.csv"

app = Flask(__name__, template_folder=str(TEMPLATE_DIR), static_folder=str(STATIC_DIR))


def load_players_from_csv(csv_path: Path) -> list[dict[str, object]]:
    players: list[dict[str, object]] = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.reader(csv_file)

        for index, row in enumerate(reader, start=1):
            if not row or all(not cell.strip() for cell in row):
                continue

            if len(row) < 2:
                raise ValueError(f"Row {index} in {csv_path.name} must include name and rating.")

            name = row[0].strip()
            skill_text = row[1].strip()

            if not name:
                raise ValueError(f"Row {index} in {csv_path.name} is missing a player name.")

            try:
                skill = round(float(skill_text), 2)
            except ValueError as error:
                raise ValueError(f"Row {index} in {csv_path.name} has an invalid rating: {skill_text}") from error

            if not 1 <= skill <= 10:
                raise ValueError(f"Row {index} in {csv_path.name} has a rating outside 1-10: {skill_text}")

            players.append(
                {
                    "id": f"player-{len(players) + 1}",
                    "name": name,
                    "skill": skill,
                    "source": "preset",
                }
            )

    if not players:
        raise ValueError(f"{csv_path.name} does not contain any players.")

    return players


PLAYERS = load_players_from_csv(RATINGS_CSV)


@dataclass(frozen=True)
class TeamCandidate:
    teams: tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]
    team_totals: tuple[float, float, float]
    averages: tuple[float, float, float]
    imbalance: float
    spread: float
    balance_penalty: float
    teammate_pairs: frozenset[tuple[str, str]]
    trios: frozenset[tuple[str, str, str]]


def team_sizes(player_count: int) -> list[int]:
    base_size = player_count // 3
    remainder = player_count % 3
    sizes = [base_size] * 3
    for index in range(remainder):
        sizes[index] += 1
    return sorted(sizes, reverse=True)


def average_skill(team: Iterable[str], roster_lookup: dict[str, dict[str, object]]) -> float:
    members = list(team)
    return sum(float(roster_lookup[player_id]["skill"]) for player_id in members) / len(members)


def team_total_skill(team: Iterable[str], roster_lookup: dict[str, dict[str, object]]) -> float:
    members = list(team)
    return sum(float(roster_lookup[player_id]["skill"]) for player_id in members)


def canonical_teams(teams: Iterable[Iterable[str]]) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    normalized = [tuple(sorted(team)) for team in teams]
    normalized.sort(key=lambda team: (-len(team), team))
    return tuple(normalized)  # type: ignore[return-value]


def build_candidate(
    teams: tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]],
    roster_lookup: dict[str, dict[str, object]],
) -> TeamCandidate:
    team_totals = tuple(team_total_skill(team, roster_lookup) for team in teams)
    averages = tuple(round(total / len(team), 2) for total, team in zip(team_totals, teams))
    imbalance = round(max(averages) - min(averages), 2)
    center = round(sum(averages) / 3, 4)
    spread = round(sum((average - center) ** 2 for average in averages), 4)
    target_team_skill = sum(team_totals) / 3
    balance_penalty = round(sum((total - target_team_skill) ** 2 for total in team_totals), 4)

    teammate_pairs = frozenset(pair for team in teams for pair in combinations(team, 2))
    trios = frozenset(trio for team in teams if len(team) >= 3 for trio in combinations(team, 3))

    return TeamCandidate(
        teams=teams,
        team_totals=team_totals,
        averages=averages,
        imbalance=imbalance,
        spread=spread,
        balance_penalty=balance_penalty,
        teammate_pairs=teammate_pairs,
        trios=trios,
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

        current_target = sum(float(roster_lookup[player_id]["skill"]) for player_id in remaining_ids) / remaining_team_count
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


def schedule_penalty(combo: tuple[TeamCandidate, ...]) -> tuple[int, int, float]:
    repeated_full_teams = sum(len(candidate.teams) for candidate in combo) - len({team for candidate in combo for team in candidate.teams})
    repeated_teammate_pairs = sum(len(candidate.teammate_pairs) for candidate in combo) - len(
        {pair for candidate in combo for pair in candidate.teammate_pairs}
    )
    balance_penalty = round(sum(candidate.balance_penalty for candidate in combo), 4)
    return repeated_full_teams, repeated_teammate_pairs, balance_penalty


def repeated_trios_across_schedule(combo: tuple[TeamCandidate, ...]) -> int:
    trio_sets = [candidate.trios for candidate in combo]

    if not trio_sets:
        return 0

    shared_trios = set(trio_sets[0]).intersection(*trio_sets[1:])
    return len(shared_trios)


def schedule_score(combo: tuple[TeamCandidate, ...]) -> tuple[int, int, int, float, float]:
    repeated_full_teams, repeated_teammate_pairs, balance_penalty = schedule_penalty(combo)
    repeated_trios = repeated_trios_across_schedule(combo)
    weighted_total = round((1000 * repeated_full_teams) + (10 * repeated_teammate_pairs) + balance_penalty, 4)
    return repeated_trios, repeated_full_teams, repeated_teammate_pairs, balance_penalty, weighted_total


def choose_suggestions(candidates: list[TeamCandidate], limit: int = 3) -> list[TeamCandidate]:
    if len(candidates) <= limit:
        return candidates

    # Exhaustively scoring every 3-candidate schedule gets expensive fast,
    # so we keep the search focused on the strongest balanced candidates.
    shortlist = candidates[: min(len(candidates), 42)]
    best_valid_combo: tuple[TeamCandidate, ...] | None = None
    best_valid_score: tuple[int, int, int, float, float] | None = None
    best_fallback_combo: tuple[TeamCandidate, ...] | None = None
    best_fallback_score: tuple[int, int, int, float, float] | None = None

    for combo in combinations(shortlist, limit):
        combo_score = schedule_score(combo)

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
        if not isinstance(skill, (int, float)) or isinstance(skill, bool) or not 1 <= float(skill) <= 10:
            raise ValueError(f"Player {name} must have a skill between 1 and 10.")
        if source not in {"preset", "guest"}:
            raise ValueError(f"Player {name} has an invalid source.")

        seen_ids.add(player_id)
        validated_players.append(
            {
                "id": player_id,
                "name": name.strip(),
                "skill": round(float(skill), 2),
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
    suggestions = choose_suggestions(candidates)
    suggestions.sort(key=lambda candidate: (candidate.imbalance, candidate.spread, candidate.teams))

    labels = ["Balanced Option 1", "Balanced Option 2", "Balanced Option 3"]
    return [
        serialize_suggestion(candidate, labels[index], roster_lookup)
        for index, candidate in enumerate(suggestions)
    ]


@app.get("/")
def index() -> str:
    return render_template("index.html", player_data_json=json.dumps(PLAYERS, ensure_ascii=False, separators=(",", ":")))


@app.post("/api/generate")
def api_generate():
    try:
        payload = request.get_json(silent=False)
        if not isinstance(payload, dict):
            raise ValueError("Invalid JSON payload.")

        selected_players = validate_selected_players(payload.get("selected_players", []))
        suggestions = generate_suggestions(selected_players)
        return jsonify({"suggestions": suggestions})
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except BadRequest:
        return jsonify({"error": "Invalid JSON payload."}), 400


if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    app.run(host=host, port=port, debug=False)
