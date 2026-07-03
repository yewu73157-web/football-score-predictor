from __future__ import annotations

import html
import json
import os
import re
from typing import Any

import requests


GOAL_LIVE_SCORES_URL = "https://www.goal.com/en-sg/live-scores"
DEFAULT_SYNC_URL = "https://gongwenjie.pythonanywhere.com/api/results/sync"
DEFAULT_SYNC_TOKEN = "football-score-odds-sync-2026"

TEAM_ALIASES = {
    "DR Congo": "民主刚果",
    "Cabo Verde": "佛得角",
    "Ivory Coast": "科特迪瓦",
    "United States": "美国",
    "Bosnia and Herzegovina": "波黑",
    "South Africa": "南非",
    "Argentina": "阿根廷",
    "Brazil": "巴西",
    "Japan": "日本",
    "Paraguay": "巴拉圭",
    "Germany": "德国",
    "Morocco": "摩洛哥",
    "Netherlands": "荷兰",
    "Norway": "挪威",
    "France": "法国",
    "Sweden": "瑞典",
    "Mexico": "墨西哥",
    "Ecuador": "厄瓜多尔",
    "England": "英格兰",
    "Belgium": "比利时",
    "Senegal": "塞内加尔",
    "Spain": "西班牙",
    "Austria": "奥地利",
    "Portugal": "葡萄牙",
    "Croatia": "克罗地亚",
    "Switzerland": "瑞士",
    "Algeria": "阿尔及利亚",
    "Australia": "澳大利亚",
    "Egypt": "埃及",
    "Colombia": "哥伦比亚",
    "Ghana": "加纳",
    "Canada": "加拿大",
}


def extract_next_data(page_html: str) -> dict[str, Any]:
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', page_html)
    if not match:
        raise RuntimeError("Goal page did not include __NEXT_DATA__")
    return json.loads(html.unescape(match.group(1)))


def parse_world_cup_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    live_scores = payload.get("props", {}).get("pageProps", {}).get("content", {}).get("liveScores", [])
    results = []
    for competition_block in live_scores:
        competition = competition_block.get("competition", {})
        if competition.get("name") != "World Cup":
            continue
        for match in competition_block.get("matches", []):
            if match.get("status") != "RESULT":
                continue
            round_name = (match.get("round") or {}).get("name", "")
            if "Final" not in round_name:
                continue
            team_a = (match.get("teamA") or {}).get("name") or (match.get("teamA") or {}).get("full")
            team_b = (match.get("teamB") or {}).get("name") or (match.get("teamB") or {}).get("full")
            score = match.get("score") or {}
            if team_a not in TEAM_ALIASES or team_b not in TEAM_ALIASES:
                continue
            if score.get("teamA") is None or score.get("teamB") is None:
                continue
            results.append(
                {
                    "home": TEAM_ALIASES[team_a],
                    "away": TEAM_ALIASES[team_b],
                    "homeGoals": int(score["teamA"]),
                    "awayGoals": int(score["teamB"]),
                    "neutral": True,
                    "matchDate": str(match.get("startDate", ""))[:10],
                }
            )
    return results


def main() -> int:
    sync_url = os.environ.get("RESULTS_SYNC_URL", DEFAULT_SYNC_URL)
    sync_token = os.environ.get("RESULTS_SYNC_TOKEN", os.environ.get("ODDS_SYNC_TOKEN", DEFAULT_SYNC_TOKEN))
    try:
        response = requests.get(GOAL_LIVE_SCORES_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        response.raise_for_status()
        results = parse_world_cup_results(extract_next_data(response.text))
        if not results:
            print("No completed World Cup final-stage results found; keeping existing results.")
            return 0
        sync_response = requests.post(
            sync_url,
            headers={"X-Results-Sync-Token": sync_token, "Content-Type": "application/json"},
            data=json.dumps({"results": results}, ensure_ascii=False).encode("utf-8"),
            timeout=20,
        )
        print(sync_response.status_code)
        print(sync_response.text[:1000])
        sync_response.raise_for_status()
    except Exception as exc:
        print(f"Results sync skipped; existing results remain active. Error: {exc}")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
