from __future__ import annotations

import math
import os
import re
import json
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from difflib import get_close_matches
from typing import Any
from urllib.parse import quote_plus

import requests
from flask import Flask, jsonify, render_template, request


app = Flask(__name__)
APP_VERSION = "20260703-auto-learning1"
SEARCH_CACHE_TTL_SECONDS = int(os.environ.get("SEARCH_CACHE_TTL_SECONDS", str(24 * 60 * 60)))
ODDS_CACHE_TTL_SECONDS = int(os.environ.get("ODDS_CACHE_TTL_SECONDS", str(30 * 60)))
ODDS_SYNC_TOKEN = os.environ.get("ODDS_SYNC_TOKEN", "football-score-odds-sync-2026")
RESULTS_SYNC_TOKEN = os.environ.get("RESULTS_SYNC_TOKEN", ODDS_SYNC_TOKEN)
SEARCH_DB_PATH = os.environ.get("SEARCH_DB_PATH", os.path.join(app.root_path, "data", "web_signals.sqlite3"))
SPORTTERY_ODDS_URL = "https://webapi.sporttery.cn/gateway/uniform/football/getMatchCalculatorV1.qry?channel=m&poolCode=had,crs"

DEFAULT_MODEL_PARAMS = {
    "market_outcome_strength": 0.38,
    "score_market_strength": 0.24,
    "clean_sheet_bias": 1.00,
    "draw_bias": 1.00,
    "high_score_bias": 1.00,
}

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 football-score-predictor/1.0 (local analytics app)",
    "Referer": "https://m.sporttery.cn/mjc/jsq/zqbf/",
    "Accept": "application/json,text/plain,*/*",
}

KNOCKOUT_TEAMS = [
    {"zh": "加拿大", "en": "Canada", "rating": 1660, "confed": "CONCACAF", "status": "已晋级16强"},
    {"zh": "南非", "en": "South Africa", "rating": 1545, "confed": "CAF", "status": "32强"},
    {"zh": "巴西", "en": "Brazil", "rating": 1905, "confed": "CONMEBOL", "status": "已晋级16强"},
    {"zh": "日本", "en": "Japan", "rating": 1725, "confed": "AFC", "status": "32强"},
    {"zh": "巴拉圭", "en": "Paraguay", "rating": 1710, "confed": "CONMEBOL", "status": "已晋级16强"},
    {"zh": "德国", "en": "Germany", "rating": 1840, "confed": "UEFA", "status": "32强"},
    {"zh": "摩洛哥", "en": "Morocco", "rating": 1740, "confed": "CAF", "status": "已晋级16强"},
    {"zh": "荷兰", "en": "Netherlands", "rating": 1845, "confed": "UEFA", "status": "32强"},
    {"zh": "挪威", "en": "Norway", "rating": 1720, "confed": "UEFA", "status": "已晋级16强"},
    {"zh": "科特迪瓦", "en": "Ivory Coast", "rating": 1620, "confed": "CAF", "status": "32强"},
    {"zh": "法国", "en": "France", "rating": 1915, "confed": "UEFA", "status": "已晋级16强"},
    {"zh": "瑞典", "en": "Sweden", "rating": 1690, "confed": "UEFA", "status": "32强"},
    {"zh": "墨西哥", "en": "Mexico", "rating": 1715, "confed": "CONCACAF", "status": "32强"},
    {"zh": "厄瓜多尔", "en": "Ecuador", "rating": 1745, "confed": "CONMEBOL", "status": "32强"},
    {"zh": "英格兰", "en": "England", "rating": 1890, "confed": "UEFA", "status": "32强"},
    {"zh": "民主刚果", "en": "DR Congo", "rating": 1565, "confed": "CAF", "status": "32强"},
    {"zh": "比利时", "en": "Belgium", "rating": 1795, "confed": "UEFA", "status": "32强"},
    {"zh": "塞内加尔", "en": "Senegal", "rating": 1695, "confed": "CAF", "status": "32强"},
    {"zh": "美国", "en": "United States", "rating": 1720, "confed": "CONCACAF", "status": "32强"},
    {"zh": "波黑", "en": "Bosnia and Herzegovina", "rating": 1600, "confed": "UEFA", "status": "32强"},
    {"zh": "西班牙", "en": "Spain", "rating": 1900, "confed": "UEFA", "status": "32强"},
    {"zh": "奥地利", "en": "Austria", "rating": 1740, "confed": "UEFA", "status": "32强"},
    {"zh": "葡萄牙", "en": "Portugal", "rating": 1865, "confed": "UEFA", "status": "32强"},
    {"zh": "克罗地亚", "en": "Croatia", "rating": 1785, "confed": "UEFA", "status": "32强"},
    {"zh": "瑞士", "en": "Switzerland", "rating": 1745, "confed": "UEFA", "status": "32强"},
    {"zh": "阿尔及利亚", "en": "Algeria", "rating": 1645, "confed": "CAF", "status": "32强"},
    {"zh": "澳大利亚", "en": "Australia", "rating": 1635, "confed": "AFC", "status": "32强"},
    {"zh": "埃及", "en": "Egypt", "rating": 1665, "confed": "CAF", "status": "32强"},
    {"zh": "阿根廷", "en": "Argentina", "rating": 1920, "confed": "CONMEBOL", "status": "32强"},
    {"zh": "佛得角", "en": "Cabo Verde", "rating": 1535, "confed": "CAF", "status": "32强"},
    {"zh": "哥伦比亚", "en": "Colombia", "rating": 1815, "confed": "CONMEBOL", "status": "32强"},
    {"zh": "加纳", "en": "Ghana", "rating": 1605, "confed": "CAF", "status": "32强"},
]

TOURNAMENT_FORM = {
    "加拿大": {"attack": 0.02, "defense": 0.10, "momentum": 0.06, "host": 0.08},
    "南非": {"attack": -0.04, "defense": 0.02, "momentum": -0.02, "host": 0.0},
    "巴西": {"attack": 0.18, "defense": 0.04, "momentum": 0.06, "host": 0.0},
    "日本": {"attack": 0.08, "defense": 0.02, "momentum": 0.02, "host": 0.0},
    "巴拉圭": {"attack": 0.02, "defense": 0.10, "momentum": 0.08, "host": 0.0},
    "德国": {"attack": 0.10, "defense": 0.00, "momentum": -0.02, "host": 0.0},
    "摩洛哥": {"attack": 0.02, "defense": 0.12, "momentum": 0.08, "host": 0.0},
    "荷兰": {"attack": 0.07, "defense": 0.04, "momentum": 0.00, "host": 0.0},
    "挪威": {"attack": 0.20, "defense": 0.02, "momentum": 0.08, "host": 0.0},
    "科特迪瓦": {"attack": 0.06, "defense": -0.02, "momentum": 0.00, "host": 0.0},
    "法国": {"attack": 0.34, "defense": 0.10, "momentum": 0.10, "host": 0.0},
    "瑞典": {"attack": 0.08, "defense": -0.02, "momentum": -0.02, "host": 0.0},
    "墨西哥": {"attack": 0.16, "defense": 0.18, "momentum": 0.14, "host": 0.18},
    "厄瓜多尔": {"attack": 0.06, "defense": 0.08, "momentum": 0.03, "host": 0.0},
    "英格兰": {"attack": 0.14, "defense": 0.08, "momentum": 0.02, "host": 0.0},
    "民主刚果": {"attack": 0.02, "defense": 0.00, "momentum": 0.04, "host": 0.0},
    "比利时": {"attack": 0.10, "defense": 0.02, "momentum": 0.00, "host": 0.0},
    "塞内加尔": {"attack": 0.06, "defense": 0.04, "momentum": 0.00, "host": 0.0},
    "美国": {"attack": 0.10, "defense": 0.04, "momentum": 0.04, "host": 0.14},
    "波黑": {"attack": 0.02, "defense": -0.02, "momentum": -0.01, "host": 0.0},
    "西班牙": {"attack": 0.20, "defense": 0.10, "momentum": 0.08, "host": 0.0},
    "奥地利": {"attack": 0.10, "defense": 0.04, "momentum": 0.06, "host": 0.0},
    "葡萄牙": {"attack": 0.16, "defense": 0.08, "momentum": 0.06, "host": 0.0},
    "克罗地亚": {"attack": 0.06, "defense": 0.06, "momentum": 0.02, "host": 0.0},
    "瑞士": {"attack": 0.06, "defense": 0.08, "momentum": 0.03, "host": 0.0},
    "阿尔及利亚": {"attack": 0.10, "defense": -0.02, "momentum": 0.06, "host": 0.0},
    "澳大利亚": {"attack": 0.04, "defense": 0.02, "momentum": 0.02, "host": 0.0},
    "埃及": {"attack": 0.08, "defense": 0.02, "momentum": 0.02, "host": 0.0},
    "阿根廷": {"attack": 0.22, "defense": 0.12, "momentum": 0.08, "host": 0.0},
    "佛得角": {"attack": 0.02, "defense": 0.02, "momentum": 0.05, "host": 0.0},
    "哥伦比亚": {"attack": 0.18, "defense": 0.06, "momentum": 0.08, "host": 0.0},
    "加纳": {"attack": 0.06, "defense": -0.02, "momentum": 0.02, "host": 0.0},
}

COMPLETED_MATCHES = [
    {"home": "加拿大", "away": "南非", "score": [1, 0], "neutral": True},
    {"home": "巴西", "away": "日本", "score": [2, 1], "neutral": True},
    {"home": "巴拉圭", "away": "德国", "score": [1, 1], "neutral": True},
    {"home": "摩洛哥", "away": "荷兰", "score": [1, 1], "neutral": True},
    {"home": "挪威", "away": "科特迪瓦", "score": [2, 1], "neutral": True},
    {"home": "法国", "away": "瑞典", "score": [3, 0], "neutral": True},
    {"home": "墨西哥", "away": "厄瓜多尔", "score": [2, 0], "neutral": False},
    {"home": "英格兰", "away": "民主刚果", "score": [2, 1], "neutral": True},
    {"home": "比利时", "away": "塞内加尔", "score": [2, 2], "neutral": True},
    {"home": "美国", "away": "波黑", "score": [2, 0], "neutral": False},
]

# Recent World Cup knockout matches are dominated by narrow wins and low-to-medium
# scorelines. The multipliers are used only for recommendation order, not for the
# displayed Poisson probabilities.
HISTORICAL_KNOCKOUT_PRIOR = {
    "1-0": 1.20,
    "0-1": 1.20,
    "2-1": 1.18,
    "1-2": 1.18,
    "2-0": 1.14,
    "0-2": 1.14,
    "1-1": 1.12,
    "0-0": 1.06,
    "3-0": 1.05,
    "0-3": 1.05,
    "3-1": 1.04,
    "1-3": 1.04,
    "2-2": 0.94,
    "3-2": 0.90,
    "2-3": 0.90,
    "4-2": 0.62,
    "2-4": 0.62,
}

TEAM_LOOKUP = {team["zh"]: team for team in KNOCKOUT_TEAMS}
TEAM_LOOKUP.update({team["en"].lower(): team for team in KNOCKOUT_TEAMS})
TEAM_ALIASES = {
    "美国队": "美国",
    "美國": "美国",
    "韩国": "韩国",
    "刚果民主共和国": "民主刚果",
    "刚果（金）": "民主刚果",
    "刚果金": "民主刚果",
    "波斯尼亚": "波黑",
    "波黑队": "波黑",
    "科特迪瓦队": "科特迪瓦",
    "象牙海岸": "科特迪瓦",
    "佛得角共和国": "佛得角",
    "卡波绿": "佛得角",
}


@dataclass
class TeamProfile:
    zh: str
    en: str
    rating: float
    confed: str
    status: str
    attack: float
    defense: float
    momentum: float
    host: float


def clean_team_name(name: str) -> str:
    raw = (name or "").strip()
    return TEAM_ALIASES.get(raw.lower(), TEAM_ALIASES.get(raw, raw))


def resolve_team(name: str) -> TeamProfile | None:
    query = clean_team_name(name)
    team = TEAM_LOOKUP.get(query) or TEAM_LOOKUP.get(query.lower())
    if not team:
        choices = list(TEAM_LOOKUP.keys())
        match = get_close_matches(query.lower(), [item.lower() for item in choices], n=1, cutoff=0.72)
        if match:
            team = TEAM_LOOKUP.get(match[0])
    if not team:
        return None
    return TeamProfile(
        zh=team["zh"],
        en=team["en"],
        rating=float(team["rating"]),
        confed=team["confed"],
        status=team["status"],
        attack=TOURNAMENT_FORM.get(team["zh"], {}).get("attack", 0.0),
        defense=TOURNAMENT_FORM.get(team["zh"], {}).get("defense", 0.0),
        momentum=TOURNAMENT_FORM.get(team["zh"], {}).get("momentum", 0.0),
        host=TOURNAMENT_FORM.get(team["zh"], {}).get("host", 0.0),
    )


def http_get(url: str, timeout: int = 8) -> str:
    response = requests.get(url, headers=HTTP_HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.text


def init_search_db() -> None:
    os.makedirs(os.path.dirname(SEARCH_DB_PATH), exist_ok=True)
    with sqlite3.connect(SEARCH_DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS web_signal_cache (
                team_key TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                fetched_at INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS odds_cache (
                cache_key TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                fetched_at INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS odds_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                payload TEXT NOT NULL,
                fetched_at INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS prediction_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_key TEXT NOT NULL,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                neutral INTEGER NOT NULL,
                payload TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS completed_results (
                match_key TEXT PRIMARY KEY,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                home_goals INTEGER NOT NULL,
                away_goals INTEGER NOT NULL,
                neutral INTEGER NOT NULL DEFAULT 1,
                source TEXT NOT NULL,
                match_date TEXT DEFAULT '',
                updated_at INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS model_params (
                name TEXT PRIMARY KEY,
                value REAL NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sync_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sync_type TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )


def log_sync_error(sync_type: str, message: str) -> None:
    init_search_db()
    with sqlite3.connect(SEARCH_DB_PATH) as conn:
        conn.execute(
            "INSERT INTO sync_errors(sync_type, message, created_at) VALUES (?, ?, ?)",
            (sync_type, message[:1000], int(time.time())),
        )


def model_params() -> dict[str, float]:
    init_search_db()
    now = int(time.time())
    with sqlite3.connect(SEARCH_DB_PATH) as conn:
        for name, value in DEFAULT_MODEL_PARAMS.items():
            conn.execute(
                "INSERT OR IGNORE INTO model_params(name, value, updated_at) VALUES (?, ?, ?)",
                (name, value, now),
            )
        rows = conn.execute("SELECT name, value FROM model_params").fetchall()
    params = dict(DEFAULT_MODEL_PARAMS)
    params.update({name: float(value) for name, value in rows})
    return params


def update_model_params(updates: dict[str, float]) -> dict[str, float]:
    init_search_db()
    now = int(time.time())
    with sqlite3.connect(SEARCH_DB_PATH) as conn:
        for name, value in updates.items():
            if name not in DEFAULT_MODEL_PARAMS:
                continue
            conn.execute(
                """
                INSERT INTO model_params(name, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (name, float(value), now),
            )
    return model_params()


def cached_payload_age(fetched_at: int) -> int:
    return max(0, int(time.time()) - int(fetched_at))


def read_cached_web_signals(team_key: str, allow_expired: bool = False) -> dict[str, Any] | None:
    init_search_db()
    with sqlite3.connect(SEARCH_DB_PATH) as conn:
        row = conn.execute(
            "SELECT payload, fetched_at FROM web_signal_cache WHERE team_key = ?",
            (team_key,),
        ).fetchone()
    if not row:
        return None
    payload = json.loads(row[0])
    age = cached_payload_age(row[1])
    if age > SEARCH_CACHE_TTL_SECONDS and not allow_expired:
        return None
    payload["cache"] = {
        "hit": True,
        "stale": age > SEARCH_CACHE_TTL_SECONDS,
        "ageSeconds": age,
        "ttlSeconds": SEARCH_CACHE_TTL_SECONDS,
    }
    return payload


def write_cached_web_signals(team_key: str, payload: dict[str, Any]) -> None:
    init_search_db()
    clean_payload = dict(payload)
    clean_payload.pop("cache", None)
    with sqlite3.connect(SEARCH_DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO web_signal_cache(team_key, payload, fetched_at)
            VALUES (?, ?, ?)
            ON CONFLICT(team_key) DO UPDATE SET
                payload = excluded.payload,
                fetched_at = excluded.fetched_at
            """,
            (team_key, json.dumps(clean_payload, ensure_ascii=False), int(time.time())),
        )


def read_cached_odds(allow_expired: bool = False) -> dict[str, Any] | None:
    init_search_db()
    with sqlite3.connect(SEARCH_DB_PATH) as conn:
        row = conn.execute(
            "SELECT payload, fetched_at FROM odds_cache WHERE cache_key = 'sporttery_had'",
        ).fetchone()
    if not row:
        return None
    payload = json.loads(row[0])
    age = cached_payload_age(row[1])
    if age > ODDS_CACHE_TTL_SECONDS and not allow_expired:
        return None
    payload["cache"] = {
        "hit": True,
        "stale": age > ODDS_CACHE_TTL_SECONDS,
        "ageSeconds": age,
        "ttlSeconds": ODDS_CACHE_TTL_SECONDS,
    }
    return payload


def write_cached_odds(payload: dict[str, Any]) -> None:
    init_search_db()
    clean_payload = dict(payload)
    clean_payload.pop("cache", None)
    payload_text = json.dumps(clean_payload, ensure_ascii=False)
    now = int(time.time())
    with sqlite3.connect(SEARCH_DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO odds_cache(cache_key, payload, fetched_at)
            VALUES ('sporttery_had', ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                payload = excluded.payload,
                fetched_at = excluded.fetched_at
            """,
            (payload_text, now),
        )
        if clean_payload.get("matches"):
            conn.execute(
                "INSERT INTO odds_snapshots(source, payload, fetched_at) VALUES (?, ?, ?)",
                (clean_payload.get("source", "unknown"), payload_text, now),
            )


def prediction_match_key(home: str, away: str) -> str:
    return f"{normalize_name_for_match(home)}::{normalize_name_for_match(away)}"


def save_prediction_snapshot(result: dict[str, Any]) -> None:
    init_search_db()
    payload = json.dumps(result, ensure_ascii=False)
    with sqlite3.connect(SEARCH_DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO prediction_snapshots(match_key, home_team, away_team, neutral, payload, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                prediction_match_key(result["homeInput"], result["awayInput"]),
                result["homeInput"],
                result["awayInput"],
                1 if result.get("neutral") else 0,
                payload,
                int(time.time()),
            ),
        )


def import_completed_results(results: list[dict[str, Any]], source: str = "GitHub Actions 自动同步赛果") -> dict[str, Any]:
    imported = 0
    init_search_db()
    with sqlite3.connect(SEARCH_DB_PATH) as conn:
        for item in results:
            home_profile = resolve_team(str(item.get("home", "")))
            away_profile = resolve_team(str(item.get("away", "")))
            if not home_profile or not away_profile:
                continue
            try:
                home_goals = int(item["homeGoals"])
                away_goals = int(item["awayGoals"])
            except (KeyError, TypeError, ValueError):
                continue
            key = prediction_match_key(home_profile.zh, away_profile.zh)
            conn.execute(
                """
                INSERT INTO completed_results(
                    match_key, home_team, away_team, home_goals, away_goals,
                    neutral, source, match_date, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(match_key) DO UPDATE SET
                    home_goals = excluded.home_goals,
                    away_goals = excluded.away_goals,
                    neutral = excluded.neutral,
                    source = excluded.source,
                    match_date = excluded.match_date,
                    updated_at = excluded.updated_at
                """,
                (
                    key,
                    home_profile.zh,
                    away_profile.zh,
                    home_goals,
                    away_goals,
                    1 if item.get("neutral", True) else 0,
                    source,
                    str(item.get("matchDate", "")),
                    int(time.time()),
                ),
            )
            imported += 1
    return {"ok": imported > 0, "imported": imported}


def completed_matches_from_db() -> list[dict[str, Any]]:
    init_search_db()
    with sqlite3.connect(SEARCH_DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT home_team, away_team, home_goals, away_goals, neutral, source, match_date
            FROM completed_results
            ORDER BY updated_at
            """
        ).fetchall()
    return [
        {
            "home": row[0],
            "away": row[1],
            "score": [int(row[2]), int(row[3])],
            "neutral": bool(row[4]),
            "source": row[5],
            "matchDate": row[6],
        }
        for row in rows
    ]


def all_completed_matches() -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for match in COMPLETED_MATCHES + completed_matches_from_db():
        merged[prediction_match_key(match["home"], match["away"])] = match
    return list(merged.values())


def latest_prediction_snapshot(match_key: str, before_ts: int | None = None) -> dict[str, Any] | None:
    init_search_db()
    sql = "SELECT payload FROM prediction_snapshots WHERE match_key = ?"
    params: list[Any] = [match_key]
    if before_ts:
        sql += " AND created_at <= ?"
        params.append(before_ts)
    sql += " ORDER BY created_at DESC LIMIT 1"
    with sqlite3.connect(SEARCH_DB_PATH) as conn:
        row = conn.execute(sql, params).fetchone()
    return json.loads(row[0]) if row else None


def tune_model_from_snapshots() -> dict[str, Any]:
    matches = completed_matches_from_db()
    if not matches:
        return {"ok": False, "reason": "暂无自动同步赛果。", "params": model_params()}
    misses = {"clean_sheet": 0, "draw": 0, "high_score": 0}
    hits = {"clean_sheet": 0, "draw": 0, "high_score": 0}
    evaluated = 0
    for match in matches[-20:]:
        snapshot = latest_prediction_snapshot(prediction_match_key(match["home"], match["away"]))
        if not snapshot:
            continue
        actual = f'{match["score"][0]}-{match["score"][1]}'
        top3 = [item["score"] for item in snapshot.get("coverageScores", {}).get("recommendedTop3", [])]
        evaluated += 1
        actual_clean = match["score"][0] == 0 or match["score"][1] == 0
        actual_draw = match["score"][0] == match["score"][1]
        actual_high = sum(match["score"]) >= 4
        predicted_clean = any(score.endswith("-0") or score.startswith("0-") for score in top3)
        predicted_draw = any(score.split("-")[0] == score.split("-")[1] for score in top3 if "-" in score)
        predicted_high = any(sum(map(int, score.split("-"))) >= 4 for score in top3 if re.fullmatch(r"\d+-\d+", score))
        for name, actual_flag, predicted_flag in [
            ("clean_sheet", actual_clean, predicted_clean),
            ("draw", actual_draw, predicted_draw),
            ("high_score", actual_high, predicted_high),
        ]:
            if actual_flag and not predicted_flag:
                misses[name] += 1
            elif actual_flag and predicted_flag:
                hits[name] += 1
    params = model_params()
    if evaluated:
        updates = dict(params)
        if misses["clean_sheet"] > hits["clean_sheet"]:
            updates["clean_sheet_bias"] = min(1.18, params["clean_sheet_bias"] + 0.02)
        if misses["draw"] > hits["draw"]:
            updates["draw_bias"] = min(1.18, params["draw_bias"] + 0.02)
        if misses["high_score"] > hits["high_score"]:
            updates["high_score_bias"] = min(1.18, params["high_score_bias"] + 0.02)
        if updates != params:
            params = update_model_params(updates)
    return {"ok": True, "evaluated": evaluated, "misses": misses, "hits": hits, "params": params}


def normalize_name_for_match(name: str) -> str:
    return re.sub(r"[\s·（）()队]", "", clean_team_name(name)).lower()


def parse_score_odds(crs: dict[str, Any]) -> dict[str, float]:
    score_odds: dict[str, float] = {}
    for key, raw_value in (crs or {}).items():
        if key.endswith("f"):
            continue
        match = re.fullmatch(r"s(\d{2})s(\d{2})", key)
        if not match:
            continue
        try:
            score_odds[f"{int(match.group(1))}-{int(match.group(2))}"] = float(raw_value)
        except (TypeError, ValueError):
            continue
    other_labels = {"s1sh": "胜其他", "s1sd": "平其他", "s1sa": "负其他"}
    for key, label in other_labels.items():
        try:
            score_odds[label] = float(crs[key])
        except (KeyError, TypeError, ValueError):
            continue
    return score_odds


def flatten_sporttery_matches(payload: dict[str, Any]) -> list[dict[str, Any]]:
    matches = []
    for date_group in payload.get("value", {}).get("matchInfoList", []):
        for match in date_group.get("subMatchList", []):
            had = match.get("had") or {}
            crs = match.get("crs") or {}
            score_odds = parse_score_odds(crs)
            try:
                odds = {
                    "home": float(had["h"]),
                    "draw": float(had["d"]),
                    "away": float(had["a"]),
                }
            except (KeyError, TypeError, ValueError):
                odds = {}
            if not odds and not score_odds:
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
                    "scoreOdds": score_odds,
                    "updatedAt": f"{had.get('updateDate', '')} {had.get('updateTime', '')}".strip(),
                    "scoreUpdatedAt": f"{crs.get('updateDate', '')} {crs.get('updateTime', '')}".strip(),
                }
            )
    return matches


def fetch_sporttery_odds() -> dict[str, Any]:
    cached = read_cached_odds()
    if cached:
        return cached
    try:
        response = requests.get(SPORTTERY_ODDS_URL, headers=HTTP_HEADERS, timeout=2.5)
        response.raise_for_status()
        payload = response.json()
        if not payload.get("success"):
            raise ValueError(payload.get("errorMessage") or "竞彩赔率接口返回失败")
        odds_payload = {
            "ok": True,
            "source": "中国体育彩票胜平负与比分公开赔率",
            "url": "https://m.sporttery.cn/mjc/jsq/zqbf/",
            "matches": flatten_sporttery_matches(payload),
            "error": "",
            "cache": {"hit": False, "ageSeconds": 0, "ttlSeconds": ODDS_CACHE_TTL_SECONDS},
        }
    except Exception as exc:
        stale = read_cached_odds(allow_expired=True)
        if stale and stale.get("ok"):
            stale["error"] = f"竞彩接口暂不可用，已使用过期缓存：{exc}"
            return stale
        odds_payload = {
            "ok": False,
            "source": "中国体育彩票胜平负与比分公开赔率",
            "url": "https://m.sporttery.cn/mjc/jsq/zqbf/",
            "matches": [],
            "error": str(exc),
            "cache": {"hit": False, "ageSeconds": 0, "ttlSeconds": ODDS_CACHE_TTL_SECONDS},
        }
    write_cached_odds(odds_payload)
    return odds_payload


def import_sporttery_odds(matches: list[dict[str, Any]], source: str = "GitHub Actions 自动同步竞彩赔率") -> dict[str, Any]:
    cleaned_matches = []
    for match in matches:
        odds = match.get("odds") or {}
        score_odds = match.get("scoreOdds") or {}
        cleaned_score_odds = {}
        for score, value in score_odds.items():
            try:
                cleaned_score_odds[str(score)] = float(value)
            except (TypeError, ValueError):
                continue
        try:
            cleaned_odds = {
                "home": float(odds["home"]),
                "draw": float(odds["draw"]),
                "away": float(odds["away"]),
            }
        except (KeyError, TypeError, ValueError):
            cleaned_odds = {}
        if not cleaned_odds and not cleaned_score_odds:
            continue
        try:
            cleaned_matches.append(
                {
                    "matchId": str(match.get("matchId", "")),
                    "matchNum": str(match.get("matchNum", "")),
                    "league": str(match.get("league", "")),
                    "matchDate": str(match.get("matchDate", "")),
                    "matchTime": str(match.get("matchTime", "")),
                    "homeTeam": str(match.get("homeTeam", "")),
                    "awayTeam": str(match.get("awayTeam", "")),
                    "odds": cleaned_odds,
                    "scoreOdds": cleaned_score_odds,
                    "updatedAt": str(match.get("updatedAt", "")),
                    "scoreUpdatedAt": str(match.get("scoreUpdatedAt", "")),
                }
            )
        except (TypeError, ValueError):
            continue
    payload = {
        "ok": bool(cleaned_matches),
        "source": source,
        "url": "https://m.sporttery.cn/mjc/jsq/zqbf/",
        "matches": cleaned_matches,
        "error": "" if cleaned_matches else "同步数据中没有可用赔率。",
        "cache": {"hit": False, "ageSeconds": 0, "ttlSeconds": ODDS_CACHE_TTL_SECONDS},
    }
    write_cached_odds(payload)
    return payload


def implied_market_probs(odds: dict[str, float]) -> dict[str, float]:
    if not {"home", "draw", "away"}.issubset(odds):
        return {}
    inv_home = 1 / odds["home"]
    inv_draw = 1 / odds["draw"]
    inv_away = 1 / odds["away"]
    total = inv_home + inv_draw + inv_away
    return {"homeWin": inv_home / total, "draw": inv_draw / total, "awayWin": inv_away / total}


def find_market_signal(home_profile: TeamProfile, away_profile: TeamProfile, use_market: bool) -> dict[str, Any]:
    if not use_market:
        return {"ok": False, "used": False, "reason": "离线模式未读取赔率。"}
    payload = fetch_sporttery_odds()
    home_key = normalize_name_for_match(home_profile.zh)
    away_key = normalize_name_for_match(away_profile.zh)
    for match in payload.get("matches", []):
        market_home = normalize_name_for_match(match.get("homeTeam", ""))
        market_away = normalize_name_for_match(match.get("awayTeam", ""))
        if home_key in market_home and away_key in market_away:
            return {
                "ok": True,
                "used": True,
                "source": payload.get("source"),
                "url": payload.get("url"),
                "match": match,
                "implied": implied_market_probs(match.get("odds") or {}),
                "cache": payload.get("cache"),
            }
        if home_key in market_away and away_key in market_home:
            raw_odds = match.get("odds") or {}
            reversed_odds = {}
            if {"home", "draw", "away"}.issubset(raw_odds):
                reversed_odds = {
                    "home": raw_odds["away"],
                    "draw": raw_odds["draw"],
                    "away": raw_odds["home"],
                }
            reversed_score_odds = {}
            for score, value in (match.get("scoreOdds") or {}).items():
                score_match = re.fullmatch(r"(\d+)-(\d+)", score)
                if score_match:
                    reversed_score_odds[f"{int(score_match.group(2))}-{int(score_match.group(1))}"] = value
                elif score == "胜其他":
                    reversed_score_odds["负其他"] = value
                elif score == "负其他":
                    reversed_score_odds["胜其他"] = value
                else:
                    reversed_score_odds[score] = value
            reversed_match = dict(match)
            reversed_match["homeTeam"] = match["awayTeam"]
            reversed_match["awayTeam"] = match["homeTeam"]
            reversed_match["odds"] = reversed_odds
            reversed_match["scoreOdds"] = reversed_score_odds
            return {
                "ok": True,
                "used": True,
                "source": payload.get("source"),
                "url": payload.get("url"),
                "match": reversed_match,
                "implied": implied_market_probs(reversed_odds),
                "cache": payload.get("cache"),
            }
    return {
        "ok": False,
        "used": False,
        "source": payload.get("source"),
        "url": payload.get("url"),
        "error": payload.get("error", ""),
        "reason": "竞彩当前列表没有匹配到这场比赛。",
        "cache": payload.get("cache"),
    }


def offline_web_signals(team: str) -> dict[str, Any]:
    return {
        "ok": False,
        "query": "",
        "items": [],
        "risk": 0.0,
        "form": 0.0,
        "signalQuality": 0.0,
        "relevantHits": 0,
        "error": "回测使用离线模式，避免页面加载时等待外网搜索。",
    }


def search_web_signals(team: str) -> dict[str, Any]:
    profile = resolve_team(team)
    search_name = profile.en if profile else clean_team_name(team)
    team_key = (profile.zh if profile else search_name).strip().lower()
    cached = read_cached_web_signals(team_key)
    if cached:
        return cached

    query = f"{search_name} World Cup 2026 injuries lineup recent form knockout"
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    try:
        html = http_get(url, timeout=2.5)
    except Exception as exc:
        stale = read_cached_web_signals(team_key, allow_expired=True)
        if stale:
            stale["error"] = f"联网搜索暂不可用，已使用过期缓存：{exc}"
            return stale
        fallback = {
            "ok": False,
            "query": query,
            "items": [],
            "risk": 0.0,
            "form": 0.0,
            "signalQuality": 0.0,
            "relevantHits": 0,
            "error": str(exc),
            "cache": {"hit": False, "ageSeconds": 0, "ttlSeconds": SEARCH_CACHE_TTL_SECONDS},
        }
        write_cached_web_signals(team_key, fallback)
        return fallback

    titles = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html, flags=re.S)
    snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, flags=re.S)
    items = []
    text_blob = ""
    team_tokens = [token for token in re.split(r"[\s-]+", search_name.lower()) if len(token) >= 4]
    relevant_hits = 0
    for title, snippet in list(zip(titles, snippets))[:6]:
        clean_title = re.sub("<.*?>", "", title)
        clean_snippet = re.sub("<.*?>", "", snippet)
        clean_title = re.sub(r"\s+", " ", clean_title).strip()
        clean_snippet = re.sub(r"\s+", " ", clean_snippet).strip()
        combined = f"{clean_title} {clean_snippet}"
        lower_combined = combined.lower()
        is_team_relevant = search_name.lower() in lower_combined or any(token in lower_combined for token in team_tokens)
        if is_team_relevant:
            relevant_hits += 1
            text_blob += " " + combined
        items.append({"title": clean_title, "snippet": clean_snippet})

    negative_words = [
        "injury",
        "injured",
        "doubt",
        "doubtful",
        "suspended",
        "absence",
        "out",
        "伤",
        "停赛",
        "缺阵",
    ]
    positive_words = ["return", "available", "fit", "back", "复出", "可出场"]
    neg = sum(text_blob.lower().count(word) for word in negative_words)
    pos = sum(text_blob.lower().count(word) for word in positive_words)
    signal_quality = min(1.0, relevant_hits / 3)
    raw_risk = (neg - pos) * 0.015 * signal_quality
    risk = max(-0.04, min(0.06, raw_risk))
    form_words = ["win", "beat", "advanced", "qualified", "unbeaten", "胜", "晋级", "不败"]
    weak_words = ["lost", "loss", "struggled", "eliminated", "defeat", "输", "出局", "低迷"]
    raw_form = (sum(text_blob.lower().count(w) for w in form_words) - sum(text_blob.lower().count(w) for w in weak_words)) * 0.01 * signal_quality
    form = max(-0.05, min(0.05, raw_form))
    payload = {
        "ok": True,
        "query": query,
        "items": items,
        "risk": risk,
        "form": form,
        "signalQuality": signal_quality,
        "relevantHits": relevant_hits,
        "cache": {"hit": False, "ageSeconds": 0, "ttlSeconds": SEARCH_CACHE_TTL_SECONDS},
    }
    write_cached_web_signals(team_key, payload)
    return payload


def poisson(k: int, lam: float) -> float:
    return math.exp(-lam) * (lam**k) / math.factorial(k)


def dc_tau(home_goals: int, away_goals: int, home_lam: float, away_lam: float, rho: float) -> float:
    if home_goals == 0 and away_goals == 0:
        return max(0.75, 1 - home_lam * away_lam * rho)
    if home_goals == 0 and away_goals == 1:
        return max(0.75, 1 + home_lam * rho)
    if home_goals == 1 and away_goals == 0:
        return max(0.75, 1 + away_lam * rho)
    if home_goals == 1 and away_goals == 1:
        return max(0.75, 1 - rho)
    return 1.0


def build_score_matrix(home_lam: float, away_lam: float) -> list[list[float]]:
    rho = -0.015
    matrix = []
    total = 0.0
    for h in range(7):
        row = []
        for a in range(7):
            value = poisson(h, home_lam) * poisson(a, away_lam) * dc_tau(h, a, home_lam, away_lam, rho)
            row.append(value)
            total += value
        matrix.append(row)
    return [[value / total for value in row] for row in matrix]


def apply_regulation_time_prior(matrix: list[list[float]]) -> list[list[float]]:
    adjusted = []
    total = 0.0
    for h, row in enumerate(matrix):
        adjusted_row = []
        for a, value in enumerate(row):
            goals = h + a
            margin = abs(h - a)
            multiplier = 1.0

            # Regular-time knockout matches are more conservative than final
            # results after extra time or penalties. Keep the correction modest.
            if h == a:
                multiplier *= 1.12
            if goals <= 2:
                multiplier *= 1.08
            if margin == 1 and goals <= 3:
                multiplier *= 1.05
            if goals >= 5:
                multiplier *= 0.78
            if goals >= 6:
                multiplier *= 0.72

            adjusted_value = value * multiplier
            adjusted_row.append(adjusted_value)
            total += adjusted_value
        adjusted.append(adjusted_row)
    return [[value / total for value in row] for row in adjusted]


def matrix_outcome_probs(matrix: list[list[float]]) -> dict[str, float]:
    home_win = draw = away_win = 0.0
    for h, row in enumerate(matrix):
        for a, value in enumerate(row):
            if h > a:
                home_win += value
            elif h == a:
                draw += value
            else:
                away_win += value
    return {"homeWin": home_win, "draw": draw, "awayWin": away_win}


def apply_market_prior(matrix: list[list[float]], market_signal: dict[str, Any], params: dict[str, float]) -> list[list[float]]:
    if not market_signal.get("ok") or not market_signal.get("implied"):
        return matrix
    implied = market_signal.get("implied") or {}
    model = matrix_outcome_probs(matrix)
    adjusted = []
    total = 0.0
    # Market odds are useful but not omniscient. A fractional exponent keeps the
    # model from blindly following crowd price moves.
    strength = params.get("market_outcome_strength", DEFAULT_MODEL_PARAMS["market_outcome_strength"])
    for h, row in enumerate(matrix):
        adjusted_row = []
        for a, value in enumerate(row):
            if h > a:
                key = "homeWin"
            elif h == a:
                key = "draw"
            else:
                key = "awayWin"
            market_prob = max(0.01, float(implied.get(key, model[key])))
            model_prob = max(0.01, model[key])
            multiplier = (market_prob / model_prob) ** strength
            adjusted_value = value * multiplier
            adjusted_row.append(adjusted_value)
            total += adjusted_value
        adjusted.append(adjusted_row)
    return [[value / total for value in row] for row in adjusted]


def apply_score_market_prior(matrix: list[list[float]], market_signal: dict[str, Any], params: dict[str, float]) -> list[list[float]]:
    if not market_signal.get("ok"):
        return matrix
    score_odds = (market_signal.get("match") or {}).get("scoreOdds") or {}
    exact_score_odds = {}
    for score, odds in score_odds.items():
        score_match = re.fullmatch(r"(\d+)-(\d+)", score)
        if not score_match:
            continue
        h = int(score_match.group(1))
        a = int(score_match.group(2))
        if h < len(matrix) and a < len(matrix[h]) and odds > 0:
            exact_score_odds[(h, a)] = float(odds)
    if len(exact_score_odds) < 5:
        return matrix

    market_inv_total = sum(1 / odds for odds in exact_score_odds.values())
    model_subset_total = sum(matrix[h][a] for h, a in exact_score_odds)
    if market_inv_total <= 0 or model_subset_total <= 0:
        return matrix

    adjusted = []
    total = 0.0
    strength = params.get("score_market_strength", DEFAULT_MODEL_PARAMS["score_market_strength"])
    for h, row in enumerate(matrix):
        adjusted_row = []
        for a, value in enumerate(row):
            score_key = (h, a)
            if score_key in exact_score_odds:
                market_prob = (1 / exact_score_odds[score_key]) / market_inv_total
                model_prob = value / model_subset_total
                multiplier = (max(0.001, market_prob) / max(0.001, model_prob)) ** strength
            else:
                multiplier = 1.0
            adjusted_value = value * multiplier
            adjusted_row.append(adjusted_value)
            total += adjusted_value
        adjusted.append(adjusted_row)
    return [[value / total for value in row] for row in adjusted]


def score_item(home_goals: int, away_goals: int, probability: float, label: str = "") -> dict[str, Any]:
    return {
        "score": f"{home_goals}-{away_goals}",
        "home": home_goals,
        "away": away_goals,
        "prob": probability,
        "label": label,
    }


def find_best_score(
    all_scores: list[dict[str, Any]],
    predicate,
    used: set[str],
    label: str,
) -> dict[str, Any] | None:
    for item in all_scores:
        if item["score"] not in used and predicate(item):
            candidate = dict(item)
            candidate["label"] = label
            return candidate
    return None


def apply_historical_prior(
    all_scores: list[dict[str, Any]],
    favorite: str,
    favorite_prob: float,
    draw: float,
    over25: float,
    btts: float,
    params: dict[str, float],
) -> list[dict[str, Any]]:
    adjusted = []
    for item in all_scores:
        candidate = dict(item)
        multiplier = HISTORICAL_KNOCKOUT_PRIOR.get(candidate["score"], 0.82)
        total_goals = candidate["home"] + candidate["away"]
        is_favorite_win = candidate["home"] > candidate["away"] if favorite == "home" else candidate["away"] > candidate["home"]
        is_clean_sheet = candidate["away"] == 0 if favorite == "home" else candidate["home"] == 0

        if is_favorite_win:
            multiplier *= 1.04
        if favorite_prob >= 0.54 and is_favorite_win and is_clean_sheet:
            multiplier *= 1.10 * params.get("clean_sheet_bias", 1.0)
        if candidate["home"] == candidate["away"]:
            multiplier *= params.get("draw_bias", 1.0)
        if btts >= 0.50 and total_goals >= 3 and candidate["home"] > 0 and candidate["away"] > 0:
            multiplier *= 1.10
        if over25 >= 0.55 and total_goals >= 3:
            multiplier *= 1.08 * params.get("high_score_bias", 1.0)
        if over25 < 0.50 and total_goals >= 4:
            multiplier *= 0.72
        if candidate["score"] == "2-2" and draw >= 0.28 and btts >= 0.45 and over25 >= 0.36:
            multiplier *= 1.65
        if candidate["score"] in {"3-2", "2-3"} and btts >= 0.50 and over25 >= 0.48 and (favorite_prob < 0.48 or draw >= 0.24):
            multiplier *= 1.55
        if candidate["score"] in {"4-2", "2-4"}:
            if over25 >= 0.68 and btts >= 0.58 and 0.50 <= favorite_prob <= 0.70:
                multiplier *= 2.25
            else:
                multiplier *= 0.45

        candidate["coverageProb"] = candidate["prob"] * multiplier
        adjusted.append(candidate)
    return sorted(adjusted, key=lambda item: item["coverageProb"], reverse=True)


def build_coverage_scores(
    all_scores: list[dict[str, Any]],
    home_win: float,
    draw: float,
    away_win: float,
    market_signal: dict[str, Any] | None = None,
    params: dict[str, float] | None = None,
) -> dict[str, Any]:
    used: set[str] = set()
    recommendations: list[dict[str, Any]] = []
    sorted_scores = sorted(all_scores, key=lambda item: item["prob"], reverse=True)
    favorite = "home" if home_win >= away_win else "away"
    favorite_margin = abs(home_win - away_win)
    favorite_prob = max(home_win, away_win)
    over25 = sum(item["prob"] for item in all_scores if item["home"] + item["away"] >= 3)
    btts = sum(item["prob"] for item in all_scores if item["home"] > 0 and item["away"] > 0)
    params = params or DEFAULT_MODEL_PARAMS
    coverage_scores = apply_historical_prior(all_scores, favorite, favorite_prob, draw, over25, btts, params)
    market_home_gap = 0.0
    market_draw = 0.0
    if market_signal and market_signal.get("ok"):
        implied = market_signal.get("implied") or {}
        market_home_gap = abs(float(implied.get("homeWin", home_win)) - float(implied.get("awayWin", away_win)))
        market_draw = float(implied.get("draw", draw))

    def add(candidate: dict[str, Any] | None) -> None:
        if candidate and candidate["score"] not in used and len(recommendations) < 3:
            used.add(candidate["score"])
            recommendations.append(candidate)

    add(dict(sorted_scores[0], label="概率最高"))
    if favorite == "home":
        before_small_win = len(recommendations)
        if btts >= 0.49:
            add(find_best_score(coverage_scores, lambda item: item["home"] > item["away"] and item["home"] - item["away"] == 1 and item["away"] > 0, used, "主队一球小胜"))
        if len(recommendations) == before_small_win:
            add(find_best_score(coverage_scores, lambda item: item["home"] > item["away"] and item["home"] - item["away"] == 1, used, "主队一球小胜"))
        if over25 >= 0.68 and btts >= 0.58 and 0.50 <= favorite_prob <= 0.70:
            add(find_best_score(coverage_scores, lambda item: item["home"] == 4 and item["away"] == 2, used, "极端大球保护"))
        elif favorite_prob >= 0.68 and over25 >= 0.60:
            add(find_best_score(coverage_scores, lambda item: item["home"] == 3 and item["away"] == 0, used, "强队零封上限"))
        elif favorite_prob >= 0.50 and away_win <= 0.27:
            add(find_best_score(coverage_scores, lambda item: item["home"] >= 2 and item["away"] == 0, used, "主队零封保护"))
        elif btts >= 0.50 and over25 >= 0.48 and (favorite_prob < 0.48 or draw >= 0.24):
            add(find_best_score(coverage_scores, lambda item: item["home"] == 3 and item["away"] == 2, used, "高比分一球差"))
        elif favorite_prob >= 0.54:
            add(find_best_score(coverage_scores, lambda item: item["home"] >= 2 and item["away"] == 0, used, "主队零封保护"))
        elif btts >= 0.50 and over25 >= 0.48:
            add(find_best_score(coverage_scores, lambda item: item["home"] > item["away"] and item["away"] > 0 and item["home"] + item["away"] >= 3, used, "双方进球保护"))
        elif favorite_prob >= 0.52:
            add(find_best_score(coverage_scores, lambda item: item["home"] >= 2 and item["away"] == 0, used, "主队零封保护"))
        else:
            add(find_best_score(coverage_scores, lambda item: item["home"] == item["away"], used, "平局保护"))
    else:
        before_small_win = len(recommendations)
        if btts >= 0.49:
            add(find_best_score(coverage_scores, lambda item: item["away"] > item["home"] and item["away"] - item["home"] == 1 and item["home"] > 0, used, "客队一球小胜"))
        if len(recommendations) == before_small_win:
            add(find_best_score(coverage_scores, lambda item: item["away"] > item["home"] and item["away"] - item["home"] == 1, used, "客队一球小胜"))
        if over25 >= 0.68 and btts >= 0.58 and 0.50 <= favorite_prob <= 0.70:
            add(find_best_score(coverage_scores, lambda item: item["away"] == 4 and item["home"] == 2, used, "极端大球保护"))
        elif favorite_prob >= 0.68 and over25 >= 0.60:
            add(find_best_score(coverage_scores, lambda item: item["away"] == 3 and item["home"] == 0, used, "强队零封上限"))
        elif favorite_prob >= 0.50 and home_win <= 0.27:
            add(find_best_score(coverage_scores, lambda item: item["away"] >= 2 and item["home"] == 0, used, "客队零封保护"))
        elif btts >= 0.50 and over25 >= 0.48 and (favorite_prob < 0.48 or draw >= 0.24):
            add(find_best_score(coverage_scores, lambda item: item["away"] == 3 and item["home"] == 2, used, "高比分一球差"))
        elif favorite_prob >= 0.54:
            add(find_best_score(coverage_scores, lambda item: item["away"] >= 2 and item["home"] == 0, used, "客队零封保护"))
        elif btts >= 0.50 and over25 >= 0.48:
            add(find_best_score(coverage_scores, lambda item: item["away"] > item["home"] and item["home"] > 0 and item["home"] + item["away"] >= 3, used, "双方进球保护"))
        elif favorite_prob >= 0.52:
            add(find_best_score(coverage_scores, lambda item: item["away"] >= 2 and item["home"] == 0, used, "客队零封保护"))
        else:
            add(find_best_score(coverage_scores, lambda item: item["home"] == item["away"], used, "平局保护"))

    for item in coverage_scores:
        add(dict(item, label="概率补位"))

    if market_signal and market_signal.get("ok") and market_home_gap >= 0.22 and market_draw <= 0.28:
        clean_sheet_score = "2-0" if favorite == "home" else "0-2"
        if clean_sheet_score not in used:
            market_clean = find_best_score(
                coverage_scores,
                lambda item: item["score"] == clean_sheet_score,
                used,
                "赔率强弱差保护",
            )
            if market_clean and recommendations:
                recommendations[-1] = market_clean
                used.add(clean_sheet_score)

    top3_scores = recommendations[:]
    top5_scores = [dict(item) for item in top3_scores]
    top5_used = {item["score"] for item in top5_scores}
    if draw >= 0.28 and btts >= 0.45 and over25 >= 0.36:
        draw_upside = find_best_score(coverage_scores, lambda item: item["score"] == "2-2", top5_used, "高比分平局保护")
        if draw_upside:
            top5_scores.append(draw_upside)
            top5_used.add(draw_upside["score"])
    for item in coverage_scores:
        if item["score"] not in top5_used:
            candidate = dict(item)
            candidate["label"] = candidate.get("label") or "保险补位"
            top5_scores.append(candidate)
            top5_used.add(candidate["score"])
        if len(top5_scores) >= 5:
            break

    top10_pool = [dict(item, label=item.get("label") or "90%候选") for item in top5_scores]
    top10_used = {item["score"] for item in top10_pool}
    if draw >= 0.28 and btts >= 0.45 and over25 >= 0.36 and "2-2" not in top10_used:
        draw_tail = find_best_score(coverage_scores, lambda item: item["score"] == "2-2", top10_used, "高比分平局保护")
        if draw_tail:
            top10_pool.append(draw_tail)
            top10_used.add(draw_tail["score"])
    if btts >= 0.45 and over25 >= 0.38 and (draw >= 0.26 or favorite_prob < 0.48):
        if favorite == "home":
            high_score_tail = find_best_score(coverage_scores, lambda item: item["home"] == 3 and item["away"] == 2, top10_used, "高比分尾部保护")
        else:
            high_score_tail = find_best_score(coverage_scores, lambda item: item["away"] == 3 and item["home"] == 2, top10_used, "高比分尾部保护")
        if high_score_tail:
            top10_pool.append(high_score_tail)
            top10_used.add(high_score_tail["score"])
    for item in coverage_scores:
        if item["score"] not in top10_used:
            candidate = dict(item)
            candidate["label"] = "90%候选"
            top10_pool.append(candidate)
            top10_used.add(candidate["score"])
        if len(top10_pool) >= 10:
            break

    upset_scores = [
        dict(item, label="冷门保护")
        for item in sorted_scores
        if (item["away"] > item["home"] if favorite == "home" else item["home"] > item["away"])
    ][:3]
    top3_mass = sum(item["prob"] for item in top3_scores)
    top5_mass = sum(item["prob"] for item in top5_scores)
    top10_mass = sum(item["prob"] for item in top10_pool)
    if favorite_prob >= 0.52 and favorite_margin >= 0.18:
        confidence = "高"
        confidence_note = "优势方较明确，主推3个可重点参考，保险5个用于覆盖零封和一球差。"
    elif favorite_prob >= 0.42 or draw >= 0.30:
        confidence = "中"
        confidence_note = "有倾向，但平局或一球差结果占比较高，建议同时看保险5个。"
    else:
        confidence = "低"
        confidence_note = "胜平负接近，杯赛波动较大，不建议只看主推3个，应看90%候选池。"

    return {
        "recommendedTop3": top3_scores,
        "recommendedTop5": top5_scores,
        "candidateTop10": top10_pool,
        "upsetProtection": upset_scores,
        "top3ProbabilityMass": top3_mass,
        "top5ProbabilityMass": top5_mass,
        "top10ProbabilityMass": top10_mass,
        "confidence": confidence,
        "confidenceNote": confidence_note,
        "coverageAdvice": "高置信看主推3个；中置信看保险5个；低置信看90%候选池。",
    }


def news_adjustment(news: dict[str, Any]) -> tuple[float, float]:
    quality = news.get("signalQuality", 0.0) if news.get("ok") else 0.0
    if quality < 0.34:
        return 0.0, 0.0
    return news.get("form", 0.0), news.get("risk", 0.0)


def collect_live_signals(
    home_profile: TeamProfile,
    away_profile: TeamProfile,
    use_web: bool,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if not use_web:
        return (
            offline_web_signals(home_profile.zh),
            offline_web_signals(away_profile.zh),
            find_market_signal(home_profile, away_profile, use_market=False),
        )

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            "home": executor.submit(search_web_signals, home_profile.zh),
            "away": executor.submit(search_web_signals, away_profile.zh),
            "market": executor.submit(find_market_signal, home_profile, away_profile, True),
        }
        try:
            home_news = futures["home"].result(timeout=3.2)
        except TimeoutError:
            home_news = offline_web_signals(home_profile.zh)
            home_news["error"] = "联网搜索超时，已跳过本场主队新闻修正。"
        try:
            away_news = futures["away"].result(timeout=3.2)
        except TimeoutError:
            away_news = offline_web_signals(away_profile.zh)
            away_news["error"] = "联网搜索超时，已跳过本场客队新闻修正。"
        try:
            market_signal = futures["market"].result(timeout=3.2)
        except TimeoutError:
            market_signal = {"ok": False, "used": False, "reason": "竞彩赔率读取超时，已跳过市场校准。"}
    return home_news, away_news, market_signal


def predict(home: str, away: str, neutral: bool, use_web: bool = True) -> dict[str, Any]:
    home_profile = resolve_team(home)
    away_profile = resolve_team(away)
    if not home_profile or not away_profile:
        valid = "、".join(team["zh"] for team in KNOCKOUT_TEAMS)
        raise ValueError(f"只能选择本届世界杯32强淘汰赛球队。可选：{valid}")
    home_news, away_news, market_signal = collect_live_signals(home_profile, away_profile, use_web)
    params = model_params()
    home_news_form, home_news_risk = news_adjustment(home_news)
    away_news_form, away_news_risk = news_adjustment(away_news)

    rating_gap = (home_profile.rating - away_profile.rating) / 400.0
    base_home = 1.32 if not neutral else 1.24
    base_away = 1.12 if not neutral else 1.24
    knockout_conservatism = -0.07
    same_confed_drag = -0.015 if home_profile.confed == away_profile.confed else 0.0
    host_home = 0.0 if neutral else home_profile.host
    host_away = 0.0 if neutral else away_profile.host
    home_lam = base_home * math.exp(
        0.44 * rating_gap
        + home_profile.attack
        - away_profile.defense
        + home_profile.momentum
        + home_news_form
        - home_news_risk
        + host_home
        + knockout_conservatism
        + same_confed_drag
    )
    away_lam = base_away * math.exp(
        -0.44 * rating_gap
        + away_profile.attack
        - home_profile.defense
        + away_profile.momentum
        + away_news_form
        - away_news_risk
        + host_away
        + knockout_conservatism
        + same_confed_drag
    )
    home_lam = max(0.25, min(4.3, home_lam))
    away_lam = max(0.25, min(4.3, away_lam))

    matrix = apply_score_market_prior(
        apply_market_prior(apply_regulation_time_prior(build_score_matrix(home_lam, away_lam)), market_signal, params),
        market_signal,
        params,
    )
    home_win = draw = away_win = over25 = btts = 0.0
    top_scores = []
    for h, row in enumerate(matrix):
        for a, p in enumerate(row):
            if h > a:
                home_win += p
            elif h == a:
                draw += p
            else:
                away_win += p
            if h + a > 2.5:
                over25 += p
            if h > 0 and a > 0:
                btts += p
            top_scores.append(score_item(h, a, p))
    top_scores.sort(key=lambda item: item["prob"], reverse=True)
    coverage = build_coverage_scores(top_scores, home_win, draw, away_win, market_signal, params)

    data_points = 2
    data_points += 1 if home_news.get("ok") else 0
    data_points += 1 if away_news.get("ok") else 0
    data_points += 1 if market_signal.get("ok") else 0
    search_quality = (home_news.get("signalQuality", 0.0) + away_news.get("signalQuality", 0.0)) / 2

    return {
        "homeInput": home_profile.zh,
        "awayInput": away_profile.zh,
        "neutral": neutral,
        "timeScope": "90分钟常规时间，不含加时赛和点球大战",
        "homeLambda": home_lam,
        "awayLambda": away_lam,
        "probabilities": {
            "homeWin": home_win,
            "draw": draw,
            "awayWin": away_win,
            "over25": over25,
            "under25": 1 - over25,
            "btts": btts,
        },
        "topScores": top_scores[:10],
        "coverageScores": coverage,
        "matrix": matrix,
        "dataQuality": {
            "score": round(data_points / 5 * 100),
            "level": "高" if data_points >= 4 else "中",
            "note": "预测口径为90分钟常规时间，不含加时赛和点球；竞彩赔率命中时会作为市场先验参与校准。",
            "searchQuality": search_quality,
            "searchNote": "搜索摘要命中球队名称时才会参与模型修正；泛化新闻会被降权。",
        },
        "sources": {
            "profiles": [home_profile.__dict__, away_profile.__dict__],
            "webSignals": [home_news, away_news],
            "marketSignal": market_signal,
            "used": [
                "2026世界杯32强淘汰赛名单",
                "国家队基础强度评分",
                "世界杯淘汰赛常见比分历史先验",
                "90分钟常规时间比分校准",
                "DuckDuckGo HTML 搜索摘要",
                "中国体育彩票胜平负公开赔率",
            ],
        },
        "generatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": {
            "version": APP_VERSION,
            "params": params,
        },
    }


def outcome(score: list[int]) -> str:
    if score[0] > score[1]:
        return "H"
    if score[0] < score[1]:
        return "A"
    return "D"


def evaluate_completed_matches() -> dict[str, Any]:
    rows = []
    result_hits = 0
    exact_hits = 0
    top5_hits = 0
    recommended3_hits = 0
    recommended5_hits = 0
    top10_hits = 0
    completed = all_completed_matches()
    for match in completed:
        result = predict(match["home"], match["away"], match["neutral"], use_web=False)
        probs = result["probabilities"]
        pmap = {"H": probs["homeWin"], "D": probs["draw"], "A": probs["awayWin"]}
        predicted_outcome = max(pmap, key=pmap.get)
        actual_outcome = outcome(match["score"])
        result_hits += predicted_outcome == actual_outcome
        top_score = result["topScores"][0]
        exact_hits += top_score["home"] == match["score"][0] and top_score["away"] == match["score"][1]

        all_scores = []
        for h, matrix_row in enumerate(result["matrix"]):
            for a, probability in enumerate(matrix_row):
                all_scores.append(((h, a), probability))
        all_scores.sort(key=lambda item: item[1], reverse=True)
        actual_rank = next(i + 1 for i, (score, _) in enumerate(all_scores) if list(score) == match["score"])
        actual_prob = next(probability for score, probability in all_scores if list(score) == match["score"])
        top5_hits += actual_rank <= 5
        actual_score_text = f'{match["score"][0]}-{match["score"][1]}'
        recommended3_scores = [item["score"] for item in result["coverageScores"]["recommendedTop3"]]
        recommended5_scores = [item["score"] for item in result["coverageScores"]["recommendedTop5"]]
        top10_scores = [item["score"] for item in result["coverageScores"]["candidateTop10"]]
        recommended3_hit = actual_score_text in recommended3_scores
        recommended5_hit = actual_score_text in recommended5_scores
        top10_hit = actual_score_text in top10_scores
        recommended3_hits += recommended3_hit
        recommended5_hits += recommended5_hit
        top10_hits += top10_hit
        rows.append(
            {
                "match": f'{match["home"]} vs {match["away"]}',
                "actualScore": actual_score_text,
                "topScore": top_score["score"],
                "topScoreProb": top_score["prob"],
                "actualScoreProb": actual_prob,
                "actualScoreRank": actual_rank,
                "predictedOutcome": predicted_outcome,
                "actualOutcome": actual_outcome,
                "outcomeHit": predicted_outcome == actual_outcome,
                "recommendedScores": recommended3_scores,
                "recommendedTop3Scores": recommended3_scores,
                "recommendedTop5Scores": recommended5_scores,
                "top10Scores": top10_scores,
                "recommendedHit": recommended3_hit,
                "recommendedTop3Hit": recommended3_hit,
                "recommendedTop5Hit": recommended5_hit,
                "top10Hit": top10_hit,
            }
        )
    total = len(completed)
    return {
        "total": total,
        "resultAccuracy": result_hits / total,
        "exactAccuracy": exact_hits / total,
        "top5Accuracy": top5_hits / total,
        "recommendedTop3Accuracy": recommended3_hits / total,
        "recommendedTop5Accuracy": recommended5_hits / total,
        "top10Accuracy": top10_hits / total,
        "rows": rows,
    }


@app.get("/")
def index():
    return render_template("index.html", teams=KNOCKOUT_TEAMS, app_version=APP_VERSION)


@app.get("/healthz")
def healthz():
    return jsonify({"ok": True, "version": APP_VERSION})


@app.get("/api/predict")
def api_predict():
    home = request.args.get("home", "").strip()
    away = request.args.get("away", "").strip()
    neutral = request.args.get("neutral", "0") == "1"
    if not home or not away:
        return jsonify({"error": "请输入两支球队名称"}), 400
    if home == away:
        return jsonify({"error": "请选择两支不同球队"}), 400
    try:
        result = predict(home, away, neutral)
        save_prediction_snapshot(result)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": f"预测失败：{exc}"}), 500


@app.get("/api/backtest")
def api_backtest():
    try:
        return jsonify(evaluate_completed_matches())
    except Exception as exc:
        return jsonify({"error": f"回测失败：{exc}"}), 500


@app.post("/api/odds/sync")
def api_odds_sync():
    token = request.headers.get("X-Odds-Sync-Token") or request.args.get("token", "")
    if token != ODDS_SYNC_TOKEN:
        return jsonify({"error": "赔率同步 token 不正确"}), 403
    payload = request.get_json(silent=True) or {}
    matches = payload.get("matches") or []
    if not isinstance(matches, list):
        return jsonify({"error": "matches 必须是数组"}), 400
    result = import_sporttery_odds(matches)
    return jsonify(
        {
            "ok": result["ok"],
            "imported": len(result["matches"]),
            "source": result["source"],
            "generatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
    )


@app.get("/api/odds/status")
def api_odds_status():
    payload = read_cached_odds(allow_expired=True)
    if not payload:
        return jsonify({"ok": False, "matches": 0, "error": "暂无赔率缓存"})
    return jsonify(
        {
            "ok": payload.get("ok", False),
            "source": payload.get("source", ""),
            "matches": len(payload.get("matches", [])),
            "cache": payload.get("cache", {}),
            "sample": payload.get("matches", [])[:5],
            "error": payload.get("error", ""),
        }
    )


@app.post("/api/results/sync")
def api_results_sync():
    token = request.headers.get("X-Results-Sync-Token") or request.headers.get("X-Odds-Sync-Token") or request.args.get("token", "")
    if token != RESULTS_SYNC_TOKEN:
        return jsonify({"error": "赛果同步 token 不正确"}), 403
    payload = request.get_json(silent=True) or {}
    results = payload.get("results") or []
    if not isinstance(results, list):
        return jsonify({"error": "results 必须是数组"}), 400
    try:
        imported = import_completed_results(results)
        tuning = tune_model_from_snapshots()
        return jsonify(
            {
                "ok": imported["ok"],
                "imported": imported["imported"],
                "tuning": tuning,
                "generatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
    except Exception as exc:
        log_sync_error("results", str(exc))
        return jsonify({"error": f"赛果同步失败：{exc}"}), 500


@app.get("/api/results/status")
def api_results_status():
    results = completed_matches_from_db()
    return jsonify(
        {
            "ok": True,
            "matches": len(results),
            "sample": results[-8:],
            "modelParams": model_params(),
        }
    )


@app.post("/api/model/tune")
def api_model_tune():
    token = request.headers.get("X-Results-Sync-Token") or request.headers.get("X-Odds-Sync-Token") or request.args.get("token", "")
    if token != RESULTS_SYNC_TOKEN:
        return jsonify({"error": "模型调参 token 不正确"}), 403
    return jsonify(tune_model_from_snapshots())


if __name__ == "__main__":
    host = os.environ.get("FOOTBALL_HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", os.environ.get("FOOTBALL_PORT", "8765")))
    debug = os.environ.get("FOOTBALL_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug)
