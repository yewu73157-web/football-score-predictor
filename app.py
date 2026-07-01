from __future__ import annotations

import math
import os
import re
import time
from dataclasses import dataclass
from difflib import get_close_matches
from functools import lru_cache
from typing import Any
from urllib.parse import quote_plus

import requests
from flask import Flask, jsonify, render_template, request


app = Flask(__name__)

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 football-score-predictor/1.0 (local analytics app)"
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
]

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


@lru_cache(maxsize=96)
def search_web_signals(team: str) -> dict[str, Any]:
    profile = resolve_team(team)
    search_name = profile.en if profile else clean_team_name(team)
    query = f"{search_name} World Cup 2026 injuries lineup recent form knockout"
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    try:
        html = http_get(url, timeout=10)
    except Exception as exc:
        return {"ok": False, "query": query, "items": [], "risk": 0.0, "error": str(exc)}

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
    return {
        "ok": True,
        "query": query,
        "items": items,
        "risk": risk,
        "form": form,
        "signalQuality": signal_quality,
        "relevantHits": relevant_hits,
    }


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


def build_coverage_scores(
    all_scores: list[dict[str, Any]],
    home_win: float,
    draw: float,
    away_win: float,
) -> dict[str, Any]:
    used: set[str] = set()
    recommendations: list[dict[str, Any]] = []
    sorted_scores = sorted(all_scores, key=lambda item: item["prob"], reverse=True)
    favorite = "home" if home_win >= away_win else "away"
    favorite_margin = abs(home_win - away_win)

    def add(candidate: dict[str, Any] | None) -> None:
        if candidate and candidate["score"] not in used and len(recommendations) < 5:
            used.add(candidate["score"])
            recommendations.append(candidate)

    add(dict(sorted_scores[0], label="概率最高"))
    add(find_best_score(sorted_scores, lambda item: item["home"] == item["away"], used, "平局保护"))
    if favorite == "home":
        add(find_best_score(sorted_scores, lambda item: item["home"] > item["away"] and item["home"] - item["away"] == 1, used, "主队小胜"))
        add(find_best_score(sorted_scores, lambda item: item["home"] >= 2 and item["away"] == 0, used, "主队零封保护"))
        add(find_best_score(sorted_scores, lambda item: item["home"] > item["away"] and item["home"] >= 2, used, "主队扩大比分"))
        if max(home_win, away_win) >= 0.50 or favorite_margin >= 0.18:
            add(find_best_score(sorted_scores, lambda item: item["home"] >= 3 and item["home"] - item["away"] >= 2, used, "强队大胜保护"))
        add(find_best_score(sorted_scores, lambda item: item["away"] > item["home"], used, "冷门保护"))
    else:
        add(find_best_score(sorted_scores, lambda item: item["away"] > item["home"] and item["away"] - item["home"] == 1, used, "客队小胜"))
        add(find_best_score(sorted_scores, lambda item: item["away"] >= 2 and item["home"] == 0, used, "客队零封保护"))
        add(find_best_score(sorted_scores, lambda item: item["away"] > item["home"] and item["away"] >= 2, used, "客队扩大比分"))
        if max(home_win, away_win) >= 0.50 or favorite_margin >= 0.18:
            add(find_best_score(sorted_scores, lambda item: item["away"] >= 3 and item["away"] - item["home"] >= 2, used, "强队大胜保护"))
        add(find_best_score(sorted_scores, lambda item: item["home"] > item["away"], used, "冷门保护"))

    add(find_best_score(sorted_scores, lambda item: item["home"] + item["away"] >= 3, used, "进攻战保护"))
    for item in sorted_scores:
        add(dict(item, label="概率补位"))

    top10_pool = sorted_scores[:10]
    upset_scores = [
        dict(item, label="冷门保护")
        for item in sorted_scores
        if (item["away"] > item["home"] if favorite == "home" else item["home"] > item["away"])
    ][:3]
    top5_mass = sum(item["prob"] for item in recommendations)
    favorite_prob = max(home_win, away_win)
    if favorite_prob >= 0.52 and favorite_margin >= 0.18:
        confidence = "高"
        confidence_note = "优势方较明确，但比分仍不能保证。"
    elif favorite_prob >= 0.42 or draw >= 0.30:
        confidence = "中"
        confidence_note = "有倾向，但平局或一球差结果占比较高。"
    else:
        confidence = "低"
        confidence_note = "胜平负接近，杯赛波动较大。"

    return {
        "recommendedTop5": recommendations,
        "candidateTop10": top10_pool,
        "upsetProtection": upset_scores,
        "top5ProbabilityMass": top5_mass,
        "confidence": confidence,
        "confidenceNote": confidence_note,
    }


def news_adjustment(news: dict[str, Any]) -> tuple[float, float]:
    quality = news.get("signalQuality", 0.0) if news.get("ok") else 0.0
    if quality < 0.34:
        return 0.0, 0.0
    return news.get("form", 0.0), news.get("risk", 0.0)


def predict(home: str, away: str, neutral: bool) -> dict[str, Any]:
    home_profile = resolve_team(home)
    away_profile = resolve_team(away)
    if not home_profile or not away_profile:
        valid = "、".join(team["zh"] for team in KNOCKOUT_TEAMS)
        raise ValueError(f"只能选择本届世界杯32强淘汰赛球队。可选：{valid}")
    home_news = search_web_signals(home)
    away_news = search_web_signals(away)
    home_news_form, home_news_risk = news_adjustment(home_news)
    away_news_form, away_news_risk = news_adjustment(away_news)

    rating_gap = (home_profile.rating - away_profile.rating) / 400.0
    base_home = 1.36 if not neutral else 1.28
    base_away = 1.16 if not neutral else 1.28
    knockout_conservatism = -0.025
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

    matrix = build_score_matrix(home_lam, away_lam)
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
    coverage = build_coverage_scores(top_scores, home_win, draw, away_win)

    data_points = 2
    data_points += 1 if home_news.get("ok") else 0
    data_points += 1 if away_news.get("ok") else 0
    search_quality = (home_news.get("signalQuality", 0.0) + away_news.get("signalQuality", 0.0)) / 2

    return {
        "homeInput": home_profile.zh,
        "awayInput": away_profile.zh,
        "neutral": neutral,
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
            "score": round(data_points / 4 * 100),
            "level": "高" if data_points >= 4 else "中",
            "note": "球队范围已限制为2026世界杯32强淘汰赛队伍；伤停/阵容来自搜索摘要，不等同于官方名单。",
            "searchQuality": search_quality,
            "searchNote": "搜索摘要命中球队名称时才会参与模型修正；泛化新闻会被降权。",
        },
        "sources": {
            "profiles": [home_profile.__dict__, away_profile.__dict__],
            "webSignals": [home_news, away_news],
            "used": [
                "2026世界杯32强淘汰赛名单",
                "国家队基础强度评分",
                "DuckDuckGo HTML 搜索摘要",
            ],
        },
        "generatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
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
    recommended_hits = 0
    for match in COMPLETED_MATCHES:
        result = predict(match["home"], match["away"], match["neutral"])
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
        recommended_scores = [item["score"] for item in result["coverageScores"]["recommendedTop5"]]
        recommended_hit = f'{match["score"][0]}-{match["score"][1]}' in recommended_scores
        recommended_hits += recommended_hit
        rows.append(
            {
                "match": f'{match["home"]} vs {match["away"]}',
                "actualScore": f'{match["score"][0]}-{match["score"][1]}',
                "topScore": top_score["score"],
                "topScoreProb": top_score["prob"],
                "actualScoreProb": actual_prob,
                "actualScoreRank": actual_rank,
                "predictedOutcome": predicted_outcome,
                "actualOutcome": actual_outcome,
                "outcomeHit": predicted_outcome == actual_outcome,
                "recommendedScores": recommended_scores,
                "recommendedHit": recommended_hit,
            }
        )
    total = len(COMPLETED_MATCHES)
    return {
        "total": total,
        "resultAccuracy": result_hits / total,
        "exactAccuracy": exact_hits / total,
        "top5Accuracy": top5_hits / total,
        "recommendedTop5Accuracy": recommended_hits / total,
        "rows": rows,
    }


@app.get("/")
def index():
    return render_template("index.html", teams=KNOCKOUT_TEAMS)


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
        return jsonify(predict(home, away, neutral))
    except Exception as exc:
        return jsonify({"error": f"预测失败：{exc}"}), 500


@app.get("/api/backtest")
def api_backtest():
    try:
        return jsonify(evaluate_completed_matches())
    except Exception as exc:
        return jsonify({"error": f"回测失败：{exc}"}), 500


if __name__ == "__main__":
    host = os.environ.get("FOOTBALL_HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", os.environ.get("FOOTBALL_PORT", "8765")))
    debug = os.environ.get("FOOTBALL_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug)
