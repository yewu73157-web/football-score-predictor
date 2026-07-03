from __future__ import annotations

import json
import os
import sys
from typing import Any

import requests


SPORTTERY_ODDS_URL = "https://webapi.sporttery.cn/gateway/uniform/football/getMatchCalculatorV1.qry?channel=m&poolCode=had"
DEFAULT_SYNC_URL = "https://gongwenjie.pythonanywhere.com/api/odds/sync"
DEFAULT_SYNC_TOKEN = "football-score-odds-sync-2026"


HEADERS = {
    "User-Agent": "Mozilla/5.0 football-score-predictor/1.0",
    "Referer": "https://m.sporttery.cn/mjc/jsq/zqspf/",
    "Accept": "application/json,text/plain,*/*",
}


def flatten_sporttery_matches(payload: dict[str, Any]) -> list[dict[str, Any]]:
    matches = []
    for date_group in payload.get("value", {}).get("matchInfoList", []):
        for match in date_group.get("subMatchList", []):
            had = match.get("had") or {}
            try:
                odds = {
                    "home": float(had["h"]),
                    "draw": float(had["d"]),
                    "away": float(had["a"]),
                }
            except (KeyError, TypeError, ValueError):
                continue
            matches.append(
                {
                    "matchId": str(match.get("matchId", "")),
                    "matchNum": match.get("matchNumStr", ""),
                    "league": match.get("leagueAllName", ""),
                    "matchDate": match.get("matchDate", ""),
                    "matchTime": match.get("matchTime", ""),
                    "homeTeam": match.get("homeTeamAllName") or match.get("homeTeamAbbName", ""),
                    "awayTeam": match.get("awayTeamAllName") or match.get("awayTeamAbbName", ""),
                    "odds": odds,
                    "updatedAt": f"{had.get('updateDate', '')} {had.get('updateTime', '')}".strip(),
                }
            )
    return matches


def main() -> int:
    sync_url = os.environ.get("ODDS_SYNC_URL", DEFAULT_SYNC_URL)
    sync_token = os.environ.get("ODDS_SYNC_TOKEN", DEFAULT_SYNC_TOKEN)

    response = requests.get(SPORTTERY_ODDS_URL, headers=HEADERS, timeout=20)
    response.raise_for_status()
    sporttery_payload = response.json()
    if not sporttery_payload.get("success"):
        raise RuntimeError(sporttery_payload.get("errorMessage") or "Sporttery odds request failed")

    matches = flatten_sporttery_matches(sporttery_payload)
    if not matches:
        raise RuntimeError("No usable odds returned from Sporttery")

    sync_response = requests.post(
        sync_url,
        headers={"X-Odds-Sync-Token": sync_token, "Content-Type": "application/json"},
        data=json.dumps({"matches": matches}, ensure_ascii=False).encode("utf-8"),
        timeout=20,
    )
    print(sync_response.status_code)
    print(sync_response.text[:1000])
    sync_response.raise_for_status()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
