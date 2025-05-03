import os
import itertools
from typing import Never

DEFAULT_RATING: float = 1000.0
FULL_WIN_VSCC_DIFF: float = 50.0

ratings: dict[str, float] = {}


class Player:
    def __init__(self, name: str, vscc_percent: float, k: float):
        self.name = name
        self.vscc_percent = vscc_percent
        self.k = k


class Modification:
    def __init__(self, modifications: dict[str, float], timestamp: int, vscc_results: list[Player] = []):
        self.modifications: dict[str, float] = modifications
        self.application_time: int = timestamp
        self.vscc_results = {p.name: p.vscc_percent for p in vscc_results} if len(vscc_results) > 0 else None

    def apply(self):
        for player, score_change in self.modifications.items():
            if not ratings.__contains__(player):
                ratings[player] = DEFAULT_RATING
            ratings[player] += score_change

    def log(self, log_path: str):
        with open(log_path, "w") as f:
            if self.vscc_results is not None:
                for player, score_change in self.modifications.items():
                    f.write(f"{player}\t{ratings[player]}\t{ratings[player]+score_change}\t{score_change:+f}\t{self.vscc_results[player]}\n")
            else:
                for player, score_change in self.modifications.items():
                    f.write(f"{player}\t{ratings[player]:4}\t{ratings[player]+score_change}\t{score_change:+f}\n")

    def log_apply(self, log_path: str):
        self.log(log_path)
        self.apply()


def outcome(vscc_1: int | float, vscc_2: int | float) -> float:
    return ((max(-FULL_WIN_VSCC_DIFF, min(vscc_2 - vscc_1, FULL_WIN_VSCC_DIFF))
            + FULL_WIN_VSCC_DIFF)
            / (FULL_WIN_VSCC_DIFF * 2))


class Game:
    def __init__(self, start_t: float, end_t: float, victor_count: int, results: list[(str, float)], name: str):
        self.start_t: int = int(start_t*100)
        self.end_t: int = int(end_t*100)
        self.victor_count: int = victor_count
        results_copy: list[(str, float)] = results.copy()
        results_copy.sort(key=lambda t: t[1], reverse=True)
        self.results: list[Player] = []
        self.name = name
        for i, (player, vscc_percent) in enumerate(results_copy):
            k = 35 + ((25 / self.victor_count) if i < self.victor_count else 0)
            self.results.append(Player(player, vscc_percent, k))

    def score(self, ratings_ref: dict[str, float]) -> Modification:
        modifications: dict[str, float] = {}
        for p1, p2 in itertools.combinations(self.results, 2):
            if p1.name not in ratings_ref:
                ratings_ref[p1.name] = DEFAULT_RATING
            if p2.name not in ratings_ref:
                ratings_ref[p2.name] = DEFAULT_RATING
            if p1.name not in modifications:
                modifications[p1.name] = 0
            if p2.name not in modifications:
                modifications[p2.name] = 0

            expected = expected_outcome(ratings_ref[p1.name] - ratings_ref[p2.name])
            actual = outcome(p1.vscc_percent, p2.vscc_percent)
            difference = expected - actual
            modifications[p1.name] += difference * p1.k
            modifications[p2.name] -= difference * p2.k
        return Modification(modifications, self.end_t, self.results)


def error(message: str) -> Never:
    print(message)
    exit(1)


def expected_outcome(diff: int | float) -> float:
    return 1 / (1 + 2 ** (diff/1000))


games: list[Game] = []
games_location = input("What folder are your game info files in?\n>>> ")
game_files = [f"{games_location}/{file_name}" for file_name in os.listdir(games_location)]
print(f"These files are being scored: {game_files}")


for path in game_files:
    vsccs: list[(str, float)] = []
    start_t, end_t, victor_count = None, None, None

    with open(path) as f:

        lines: list[str] = f.readlines()
        if len(lines) <= 4:
            error(f"Error: too few lines in {path}. Each file must at least have 3 lines for the "
                  "start time, end time, and victor count (0 for a draw), in that order, and then "
                  "data for at least two countries.")
        try:
            start_t = float(lines.pop(0))
            assert start_t >= 0
            end_t = float(lines.pop(0))
            assert end_t >= 0
            victor_count = int(lines.pop(0))
            assert victor_count >= 0
        except Exception:
            error(f"Error: header in file {path} was not formatted correctly. Files need a header "
                  "with start time (month.day), end time (month.day), and victor count (0 for draw), "
                  "in that order. \"month\" means number of months since January 2024, \"day\" means "
                  "2-digit day of the month. For example, a start time could be 13.01, meaning January "
                  "1, 2025.")
        line_counter: int = 3
        for line in lines:
            line_counter += 1

            parts = line.split('\t')
            if len(parts) != 2:
                error(f"Error: file {path} line #{line_counter} had the wrong format. "
                      "Each line after the header should contain the original player discord tag "
                      "and vscc%, in that order, with tabs between them.")

            original_player, score = parts
            for o_p, _ in vsccs:
                if o_p == original_player:
                    error(f"Error: file {path} contained two nations played by the same player.")
            try:
                score = float(score)
            except Exception:
                error(f"Error: file {path} line {line_counter}'s score (second item) was not a number. "
                      "Each line after the header should contain the original player discord tag,"
                      "and vscc%, in that order, with tabs between them.")
            vsccs.append((original_player, score))
    if len(vsccs) < 24 or len(vsccs) > 25:
        print(f"Warning: file {path} contained information for less than 24 or over 25 players. "
              "Imperial diplomacy has 24-25 players (depending on the wave), so this seems likely"
              "to be a mistake.")
    games.append(Game(start_t, end_t, victor_count, vsccs, path))

modifications_stack: list[(Modification, str)] = []
the_time: int = -1
games.sort(key=lambda g: g.start_t * 10000)
while True:
    the_time += 1

    for _ in range(len(modifications_stack)):
        if modifications_stack[0][0].application_time == the_time:
            m = modifications_stack.pop(0)
            m[0].log_apply(m[1] + "_results.txt")

    for _ in range(len(games)):
        if games[0].start_t == the_time:
            game = games.pop(0)
            to_append = game.score(ratings), game.name
            modifications_stack.append(to_append)
        else:
            break  # `games` is sorted by `start_t`

    if len(games) == 0:
        for modification, output_file in modifications_stack:
            modification.log_apply(output_file+"_results.txt")
        break

with open("current_ratings.txt", "w") as f:
    ratings_list = list(ratings.items())
    ratings_list.sort(key=lambda t:t[1], reverse=True)
    for player, rating in ratings_list:
        f.write(f"{player}\t{rating}\n")