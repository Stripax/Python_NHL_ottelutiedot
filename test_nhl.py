"""Analyysin, tallennuksen ja API-virheiden regressiotestit ilman verkkoa."""

import csv
import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

import nhl


def raw_game(identifier=1, state="OFF", home=3, away=1, outcome="REG"):
    return {"id": identifier, "gameDate": "2025-01-01", "startTimeUTC": "2025-01-01T23:00:00Z",
            "gameState": state, "homeTeam": {"abbrev": "LAK", "score": home},
            "awayTeam": {"abbrev": "NJD", "score": away},
            "gameOutcome": {"lastPeriodType": outcome}}


class NHLTests(unittest.TestCase):
    def test_statistics_exclude_unfinished_games(self):
        games = [nhl.normalize_game(raw_game()),
                 nhl.normalize_game(raw_game(2, "FINAL", 2, 3, "OT")),
                 nhl.normalize_game(raw_game(3, "LIVE", 8, 8)),
                 nhl.normalize_game(raw_game(4, "FUT", None, None))]
        stats = nhl.analyze_games(games)
        self.assertEqual(stats["finished_games"], 2)
        self.assertEqual(stats["total_goals"], 9)
        self.assertEqual(stats["average_goals"], 4.5)
        self.assertEqual(stats["home_win_percentage"], 50)
        self.assertEqual(stats["average_goal_difference"], 1.5)
        self.assertEqual(stats["overtime_percentage"], 50)
        self.assertEqual(stats["highest_scoring_games"][0]["id"], 2)

    def test_empty_and_future_only(self):
        for games in ([], [nhl.normalize_game(raw_game(state="FUT", home=None, away=None))]):
            stats = nhl.analyze_games(games)
            self.assertIsNone(stats["average_goals"])
            self.assertIsNone(stats["home_win_percentage"])
            with patch("sys.stdout", new_callable=io.StringIO) as output:
                nhl.print_report(games, stats)
                self.assertIn("ei ole päättyneitä", output.getvalue())

    def test_unknown_outcome_not_treated_as_regulation(self):
        stats = nhl.analyze_games([nhl.normalize_game(raw_game(outcome=None))])
        self.assertIsNone(stats["overtime_percentage"])
        self.assertEqual(stats["finished_games"], 1)

    def test_invalid_final_scores_rejected(self):
        for home, away in ((None, 1), (-1, 1), (True, 1), (2, 2)):
            with self.assertRaises(nhl.NHLDataError):
                nhl.normalize_game(raw_game(home=home, away=away))

    def test_json_and_csv_roundtrip(self):
        games = [nhl.normalize_game(raw_game(state="FUT", home=None, away=None))]
        day = date(2025, 1, 1)
        with tempfile.TemporaryDirectory() as directory:
            for suffix in ("json", "csv"):
                path = Path(directory) / f"nested/results.{suffix}"
                nhl.save_games(games, path, day, day)
                with path.open(encoding="utf-8", newline="") as handle:
                    if suffix == "json":
                        self.assertEqual(json.load(handle)["games"], games)
                    else:
                        rows = list(csv.DictReader(handle))
                        self.assertEqual(rows[0]["home_score"], "")
                        self.assertEqual(rows[0]["away_team"], "NJD")

    @patch("nhl.urlopen")
    def test_range_requests_and_deduplication(self, mock_open):
        day = date(2025, 1, 1)
        mock_open.side_effect = [io.StringIO(json.dumps({"games": [raw_game(), raw_game()]})),
                                 io.StringIO(json.dumps({"games": []}))]
        games = nhl.fetch_games(day, date(2025, 1, 2))
        self.assertEqual(len(games), 1)
        self.assertEqual(mock_open.call_count, 2)
        self.assertTrue(mock_open.call_args.args[0].full_url.endswith("2025-01-02"))

    @patch("nhl.urlopen")
    def test_bad_api_responses(self, mock_open):
        day = date(2025, 1, 1)
        for payload in ("bad json", "{}", '{"games": null}', '{"games": [{}]}'):
            mock_open.return_value = io.StringIO(payload)
            with self.assertRaises(nhl.NHLDataError):
                nhl.fetch_games(day, day)
        mock_open.side_effect = URLError("offline")
        with self.assertRaises(nhl.NHLDataError):
            nhl.fetch_games(day, day)

    @patch("nhl.fetch_games")
    def test_invalid_arguments_fail_before_network(self, fetch):
        for args in (["--start", "invalid"], ["--start", "2025-02-01", "--end", "2025-01-01"],
                     ["--output", "results.txt"]):
            with patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit):
                nhl.main(args)
        fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
