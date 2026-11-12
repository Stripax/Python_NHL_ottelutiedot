"""Hae NHL-ottelut ja analysoi tulokset Pythonin vakiokirjastolla."""

import argparse
import csv
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_URL = "https://api-web.nhle.com/v1/score"
FINAL_STATES = {"FINAL", "OFF"}
FIELDS = ["id", "date", "start_time_utc", "away_team", "home_team",
          "away_score", "home_score", "state", "last_period_type"]


class NHLDataError(Exception):
    """Rajapinnan vastausta ei voida käyttää."""


def normalize_game(game):
    """Poimi tallennukseen ja analyysiin tarvittavat kentät."""
    try:
        row = {
            "id": game["id"],
            "date": game["gameDate"],
            "start_time_utc": game["startTimeUTC"],
            "away_team": game["awayTeam"]["abbrev"],
            "home_team": game["homeTeam"]["abbrev"],
            "away_score": game["awayTeam"].get("score"),
            "home_score": game["homeTeam"].get("score"),
            "state": game["gameState"],
            "last_period_type": game.get("gameOutcome", {}).get("lastPeriodType"),
        }
        if type(row["id"]) is not int:
            raise ValueError("Ottelun tunniste puuttuu tai on virheellinen")
        for field in ("away_score", "home_score"):
            value = row[field]
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("Virheellinen maalimäärä")
        if row["state"] in FINAL_STATES:
            if row["away_score"] is None or row["home_score"] is None:
                raise ValueError("Päättyneen ottelun tulos puuttuu")
            if row["away_score"] == row["home_score"]:
                raise ValueError("Päättyneen NHL-ottelun tulos on tasan")
        return row
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise NHLDataError(f"Virheellinen ottelutieto: {exc}") from exc


def fetch_games(start, end):
    """Hae kukin päivä erikseen; virhe keskeyttää koko haun."""
    games = {}
    current = start
    while current <= end:
        url = f"{API_URL}/{current.isoformat()}"
        request = Request(url, headers={"User-Agent": "NHLResults/1.0", "Accept": "application/json"})
        try:
            with urlopen(request, timeout=30) as response:
                payload = json.load(response)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            raise NHLDataError(f"Haku epäonnistui ({current}): {exc}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("games"), list):
            raise NHLDataError(f"Rajapinnan vastaus ei sisällä ottelulistaa ({current}).")
        for raw in payload["games"]:
            game = normalize_game(raw)
            if start.isoformat() <= game["date"] <= end.isoformat():
                games[game["id"]] = game
        if current == end:
            break
        current += timedelta(days=1)
    return sorted(games.values(), key=lambda game: (game["date"], game["id"]))


def analyze_games(games):
    """Laske tunnusluvut vain päättyneiden otteluiden lopputuloksista."""
    finished = [game for game in games if game["state"] in FINAL_STATES]
    count = len(finished)
    home_goals = sum(game["home_score"] for game in finished)
    away_goals = sum(game["away_score"] for game in finished)
    home_wins = sum(game["home_score"] > game["away_score"] for game in finished)
    known_outcomes = [game for game in finished if game["last_period_type"] in {"REG", "OT", "SO"}]
    overtime = sum(game["last_period_type"] in {"OT", "SO"} for game in known_outcomes)
    most_goals = max((g["home_score"] + g["away_score"] for g in finished), default=None)
    return {
        "fetched_games": len(games),
        "finished_games": count,
        "total_goals": home_goals + away_goals,
        "average_goals": (home_goals + away_goals) / count if count else None,
        "home_wins": home_wins,
        "home_win_percentage": 100 * home_wins / count if count else None,
        "average_goal_difference": sum(abs(g["home_score"] - g["away_score"]) for g in finished) / count if count else None,
        "overtime_games": overtime,
        "known_outcomes": len(known_outcomes),
        "overtime_percentage": 100 * overtime / len(known_outcomes) if known_outcomes else None,
        "highest_scoring_games": [g for g in finished if g["home_score"] + g["away_score"] == most_goals],
    }


def save_games(games, output, start, end):
    """Tallenna UTF-8-muodossa; tiedostopääte määrää formaatin."""
    output = Path(output)
    if output.suffix.lower() not in {".json", ".csv"}:
        raise ValueError("Tulostiedoston päätteen tulee olla .json tai .csv.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        if output.suffix.lower() == ".csv":
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(games)
        else:
            json.dump({
                "source": API_URL,
                "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                "start_date": start.isoformat(), "end_date": end.isoformat(),
                "games": games,
            }, handle, ensure_ascii=False, indent=2)
            handle.write("\n")


def print_report(games, stats):
    print("\nNHL-ottelut (vieras – koti)")
    print("Päivämäärä  Ottelu         Tulos  Tila")
    labels = {"OFF": "Päättynyt", "FINAL": "Päättynyt", "FUT": "Tulossa",
              "PRE": "Alkamassa", "LIVE": "Käynnissä", "CRIT": "Käynnissä"}
    for game in games:
        score = f"{game['away_score']}–{game['home_score']}" if game["away_score"] is not None and game["home_score"] is not None else "–"
        print(f"{game['date']}  {game['away_team']:>3} – {game['home_team']:<3}    {score:>5}  {labels.get(game['state'], game['state'])}")
    print(f"\nHaettuja otteluita: {stats['fetched_games']}")
    print(f"Päättyneitä otteluita: {stats['finished_games']}")
    if not stats["finished_games"]:
        print("Analyysiä ei voi laskea: aikavälillä ei ole päättyneitä otteluita.")
        return
    print(f"Maalit yhteensä: {stats['total_goals']}")
    print(f"Maaleja keskimäärin / ottelu: {stats['average_goals']:.2f}")
    print(f"Kotivoittojen osuus: {stats['home_win_percentage']:.1f} % ({stats['home_wins']} voittoa)")
    print(f"Keskimääräinen maaliero: {stats['average_goal_difference']:.2f}")
    if stats["overtime_percentage"] is not None:
        print(f"Jatkoajalle tai voittolaukauksiin: {stats['overtime_percentage']:.1f} % "
              f"({stats['overtime_games']}/{stats['known_outcomes']} ottelua, joiden ratkaisutapa tunnetaan)")
    else:
        print("Jatkoaikaosuutta ei voi laskea: ratkaisutapatiedot puuttuvat.")
    print("\nAnalyysi:")
    percentage = stats["home_win_percentage"]
    if percentage == 50:
        print("Koti- ja vierasjoukkueet voittivat yhtä usein tässä aineistossa.")
    else:
        winner = "Kotijoukkueet" if percentage > 50 else "Vierasjoukkueet"
        print(f"{winner} voittivat useammin tässä aineistossa.")
    print("Runsasmaalisimmat ottelut:")
    for game in stats["highest_scoring_games"]:
        print(f"  {game['date']}: {game['away_team']} – {game['home_team']} "
              f"{game['away_score']}–{game['home_score']}")
    print("Tunnusluvut perustuvat päättyneiden otteluiden tulostaulun maaleihin, myös voittolaukauskilpailun ratkaisumaaliin.")
    print("Tulokset kuvaavat valittua aineistoa; ne eivät ennusta tulevia otteluita.")


def parse_date(value):
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Anna päivämäärä muodossa VVVV-KK-PP.") from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description="Hae NHL-ottelut, tallenna ne ja näytä tulosanalyysi.")
    parser.add_argument("--start", type=parse_date, default=date.today() - timedelta(days=1), help="Alkupäivä VVVV-KK-PP (oletus: eilinen).")
    parser.add_argument("--end", type=parse_date, help="Loppupäivä, mukaan lukien (oletus: alkupäivä).")
    parser.add_argument("--output", type=Path, help="JSON- tai CSV-tiedosto (olemassa oleva tiedosto korvataan).")
    args = parser.parse_args(argv)
    end = args.end or args.start
    if end < args.start:
        parser.error("Loppupäivä ei voi olla ennen alkupäivää.")
    if (end - args.start).days >= 366:
        parser.error("Voit hakea enintään 366 päivää kerralla.")
    output = args.output or Path("data") / f"nhl_{args.start}_{end}.json"
    if output.suffix.lower() not in {".json", ".csv"}:
        parser.error("Tulostiedoston päätteen tulee olla .json tai .csv.")
    print(f"Haetaan ottelut ajalta {args.start} – {end}…")
    try:
        games = fetch_games(args.start, end)
        stats = analyze_games(games)
        save_games(games, output, args.start, end)
    except (NHLDataError, OSError, ValueError) as exc:
        print(f"Virhe: {exc}", file=sys.stderr)
        return 1
    print(f"Tallennettu: {output.resolve()}")
    print_report(games, stats)
    return 0


if __name__ == "__main__":
    # UTF-8 säilyttää ääkköset myös Windowsin uudelleenohjatussa tulosteessa.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
