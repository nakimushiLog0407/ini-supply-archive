#!/usr/bin/env python3

import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from zoneinfo import ZoneInfo

import requests


TIMEOUT = 30
REQUEST_INTERVAL = 1.0

SYNDICATION_ENDPOINT = (
    "https://cdn.syndication.twimg.com/tweet-result"
)

USER_AGENT = (
    "Mozilla/5.0 "
    "(X11; Linux x86_64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/140.0.0.0 "
    "Safari/537.36"
)

DATA_FILES = [
    ("schedule", Path("data/schedule.json")),
    ("youtube", Path("data/youtube.json")),
    ("member_diary", Path("data/member_diary.json")),
    ("message", Path("data/message.json")),
    ("movie", Path("data/movie.json")),
    ("photo", Path("data/photo.json")),
    ("radio", Path("data/radio.json")),
]

FC_TYPES = {
    "member_diary",
    "message",
    "movie",
    "photo",
    "radio",
}

MEMBER_ALIASES = {
    "池﨑理人": ["池﨑理人", "理人", "RIHITO"],
    "尾崎匠海": ["尾崎匠海", "匠海", "TAKUMI"],
    "木村柾哉": ["木村柾哉", "柾哉", "MASAYA"],
    "後藤威尊": ["後藤威尊", "威尊", "TAKERU"],
    "佐野雄大": ["佐野雄大", "雄大", "YUDAI"],
    "シュウ・フェンファン": [
        "シュウ・フェンファン",
        "許豊凡",
        "フェンファン",
        "FENGFAN",
    ],
    "髙塚大夢": ["髙塚大夢", "高塚大夢", "大夢", "HIROMU"],
    "田島将吾": ["田島将吾", "将吾", "SHOGO"],
    "西洸人": ["西洸人", "洸人", "HIROTO"],
    "藤牧京介": ["藤牧京介", "京介", "KYOSUKE"],
    "松田迅": ["松田迅", "迅", "JIN"],
}


def section(title):
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def normalize_text(value):
    if value is None:
        return ""

    value = unicodedata.normalize(
        "NFKC",
        str(value),
    )

    value = value.lower()

    value = re.sub(
        r"https?://\S+",
        " ",
        value,
    )

    value = re.sub(
        r"[@#＃]",
        "",
        value,
    )

    value = re.sub(
        r"[\s　]+",
        " ",
        value,
    )

    return value.strip()


def compact_text(value):
    value = normalize_text(value)

    value = re.sub(
        r"[^0-9a-zぁ-んァ-ヶ一-龯髙﨑]+",
        "",
        value,
    )

    return value


def normalize_x_url(url):
    match = re.search(
        r"https?://(?:www\.)?(?:x|twitter)\.com/"
        r"([^/\s]+)/status/(\d+)",
        url.strip(),
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    return {
        "post_id": match.group(2),
        "url": (
            f"https://x.com/"
            f"{match.group(1)}/status/{match.group(2)}"
        ),
    }


def parse_urls(raw):
    unique = []
    seen = set()

    for token in re.split(r"\s+", raw.strip()):
        if not token:
            continue

        item = normalize_x_url(token)

        if not item:
            continue

        if item["post_id"] in seen:
            continue

        seen.add(item["post_id"])
        unique.append(item)

    return unique


def convert_to_jst(created_at):
    if not created_at:
        return None

    dt = datetime.fromisoformat(
        created_at.replace(
            "Z",
            "+00:00",
        )
    )

    return dt.astimezone(
        ZoneInfo("Asia/Tokyo")
    )


def fetch_post(item):
    response = requests.get(
        SYNDICATION_ENDPOINT,
        params={
            "id": item["post_id"],
            "lang": "ja",
            "token": "0",
        },
        timeout=TIMEOUT,
        headers={
            "User-Agent": USER_AGENT,
        },
    )

    response.raise_for_status()

    data = response.json()

    if not data:
        return None

    created = convert_to_jst(
        data.get("created_at")
    )

    user = data.get("user") or {}

    return {
        "post_id": item["post_id"],
        "url": item["url"],
        "text": data.get("text") or "",
        "created_at_jst": created,
        "author": user.get("screen_name"),
    }


def load_json(path):
    try:
        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if isinstance(data, list):
            return data

        return []

    except Exception as exc:
        print(
            f"WARNING: {path}: {exc}"
        )
        return []


def load_existing_data():
    all_items = []

    section("LOAD EXISTING DATA")

    for source_type, path in DATA_FILES:
        items = load_json(path)

        print(
            f"{source_type}: {len(items)}"
        )

        for item in items:
            if not isinstance(item, dict):
                continue

            copy = dict(item)
            copy["_source_type"] = source_type

            all_items.append(copy)

    print()
    print(
        "TOTAL:",
        len(all_items),
    )

    return all_items


def parse_date(value):
    if not value:
        return None

    text = str(value)

    match = re.search(
        r"(\d{4})-(\d{2})-(\d{2})",
        text,
    )

    if not match:
        return None

    try:
        return datetime(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
        ).date()

    except ValueError:
        return None


def get_item_date(item):
    for key in [
        "date",
        "publishedAt",
        "published_at",
        "startDate",
        "start_date",
        "datetime",
    ]:
        date = parse_date(
            item.get(key)
        )

        if date:
            return date

    return None


def get_item_title(item):
    for key in [
        "title",
        "name",
        "program",
        "programName",
        "program_name",
    ]:
        value = item.get(key)

        if value:
            return str(value)

    return ""


def extract_members(text):
    compact = compact_text(text)

    result = []

    for canonical, aliases in MEMBER_ALIASES.items():
        for alias in aliases:
            if compact_text(alias) in compact:
                result.append(canonical)
                break

    return result


def title_similarity(post_text, item_title):
    post = compact_text(post_text)
    title = compact_text(item_title)

    if not post or not title:
        return 0.0

    if title in post:
        return 1.0

    ratio = SequenceMatcher(
        None,
        post,
        title,
    ).ratio()

    return ratio


def extract_quoted_phrases(text):
    patterns = [
        r"「([^」]{2,80})」",
        r"'([^']{2,80})'",
        r'"([^"]{2,80})"',
    ]

    phrases = []

    for pattern in patterns:
        phrases.extend(
            re.findall(
                pattern,
                text,
            )
        )

    return phrases


def phrase_match_score(post_text, title):
    title_compact = compact_text(title)

    if not title_compact:
        return 0.0

    best = 0.0

    for phrase in extract_quoted_phrases(
        post_text
    ):
        phrase_compact = compact_text(
            phrase
        )

        if not phrase_compact:
            continue

        if (
            phrase_compact in title_compact
            or title_compact in phrase_compact
        ):
            best = max(
                best,
                1.0,
            )
            continue

        score = SequenceMatcher(
            None,
            phrase_compact,
            title_compact,
        ).ratio()

        best = max(
            best,
            score,
        )

    return best


def calculate_candidate_score(
    post,
    item,
):
    post_date = (
        post["created_at_jst"].date()
        if post.get("created_at_jst")
        else None
    )

    item_date = get_item_date(
        item
    )

    title = get_item_title(
        item
    )

    source_type = item.get(
        "_source_type",
        ""
    )

    score = 0.0
    reasons = []

    # ----------------------------------------
    # タイトル
    # ----------------------------------------

    title_score = title_similarity(
        post["text"],
        title,
    )

    phrase_score = phrase_match_score(
        post["text"],
        title,
    )

    effective_title_score = max(
        title_score,
        phrase_score,
    )

    if effective_title_score >= 0.90:
        score += 60
        reasons.append(
            "title:strong"
        )

    elif effective_title_score >= 0.70:
        score += 45
        reasons.append(
            "title:medium"
        )

    elif effective_title_score >= 0.50:
        score += 25
        reasons.append(
            "title:weak"
        )

    # ----------------------------------------
    # 日付
    # ----------------------------------------

    if post_date and item_date:
        difference = abs(
            (post_date - item_date).days
        )

        if difference == 0:
            score += 25
            reasons.append(
                "date:same"
            )

        elif difference <= 1:
            score += 15
            reasons.append(
                "date:±1"
            )

        elif difference <= 7:
            score += 5
            reasons.append(
                "date:near"
            )

    # ----------------------------------------
    # メンバー
    # ----------------------------------------

    post_members = set(
        extract_members(
            post["text"]
        )
    )

    item_text = " ".join(
        str(item.get(key) or "")
        for key in [
            "title",
            "member",
            "members",
            "detail",
            "description",
        ]
    )

    item_members = set(
        extract_members(
            item_text
        )
    )

    common_members = (
        post_members
        & item_members
    )

    if common_members:
        score += min(
            15,
            5 * len(common_members),
        )

        reasons.append(
            "member:"
            + ",".join(
                sorted(common_members)
            )
        )

    # ----------------------------------------
    # FC固有キーワード
    # ----------------------------------------

    post_normalized = normalize_text(
        post["text"]
    )

    if source_type == "member_diary":
        if "member diary" in post_normalized:
            score += 30
            reasons.append(
                "fc:member_diary"
            )

    if source_type == "message":
        if (
            "type check" in post_normalized
            or "message" in post_normalized
        ):
            score += 25
            reasons.append(
                "fc:message"
            )

    if source_type == "movie":
        if "movie" in post_normalized:
            score += 20
            reasons.append(
                "fc:movie"
            )

    if source_type == "radio":
        if (
            "web radio" in post_normalized
            or "radio" in post_normalized
        ):
            score += 20
            reasons.append(
                "fc:radio"
            )

    return {
        "score": round(
            score,
            1,
        ),
        "reasons": reasons,
        "title": title,
        "date": (
            item_date.isoformat()
            if item_date
            else None
        ),
        "source_type": source_type,
        "id": item.get("id"),
        "url": item.get("url"),
    }


def find_candidates(
    post,
    existing,
):
    post_date = (
        post["created_at_jst"].date()
        if post.get("created_at_jst")
        else None
    )

    candidates = []

    for item in existing:
        item_date = get_item_date(
            item
        )

        # X投稿日前後14日だけを基本検索範囲にする。
        # 将来日の出演告知もあるため、
        # 投稿後14日まで許容する。
        if post_date and item_date:
            delta = (
                item_date - post_date
            ).days

            if delta < -7 or delta > 14:
                continue

        candidate = (
            calculate_candidate_score(
                post,
                item,
            )
        )

        if candidate["score"] >= 25:
            candidates.append(
                candidate
            )

    candidates.sort(
        key=lambda x: x["score"],
        reverse=True,
    )

    return candidates[:5]


def preliminary_classification(
    post,
    candidates,
):
    text = normalize_text(
        post["text"]
    )

    if candidates:
        top = candidates[0]

        if top["score"] >= 60:
            return (
                "existing_content_candidate"
            )

    schedule_words = [
        "出演",
        "生出演",
        "放送",
        "radio",
        "ラジオ",
        "テレビ",
        "nhk",
        "日本テレビ",
        "フジテレビ",
        "stationhead",
        "listening party",
    ]

    if any(
        word in text
        for word in schedule_words
    ):
        return "new_schedule_candidate"

    excluded_words = [
        "受注販売",
        "販売スタート",
        "ご購入",
        "購入いただけます",
    ]

    if any(
        word in text
        for word in excluded_words
    ):
        return "exclude_candidate"

    return "x_content_candidate"


def preview(text, limit=180):
    value = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    if len(value) > limit:
        return (
            value[:limit]
            + "..."
        )

    return value


def print_result(
    index,
    total,
    post,
    candidates,
):
    section(
        f"POST {index}/{total}"
    )

    print(
        "POST ID:",
        post["post_id"],
    )

    print(
        "POSTED:",
        post["created_at_jst"].isoformat(),
    )

    print()
    print("TEXT:")
    print(
        post["text"]
    )

    classification = (
        preliminary_classification(
            post,
            candidates,
        )
    )

    print()
    print(
        "PRELIMINARY CLASSIFICATION:",
        classification,
    )

    print()
    print("MATCH CANDIDATES:")

    if not candidates:
        print(
            "(none)"
        )
        return

    for number, candidate in enumerate(
        candidates,
        start=1,
    ):
        print()
        print(
            f"  [{number}] "
            f"SCORE={candidate['score']}"
        )

        print(
            "      TYPE:",
            candidate["source_type"],
        )

        print(
            "      ID:",
            candidate["id"],
        )

        print(
            "      DATE:",
            candidate["date"],
        )

        print(
            "      TITLE:",
            candidate["title"],
        )

        print(
            "      REASONS:",
            ", ".join(
                candidate["reasons"]
            ),
        )


def main():
    section(
        "X EXISTING CONTENT MATCH DIAGNOSTIC"
    )

    raw_urls = os.environ.get(
        "X_URLS",
        "",
    ).strip()

    if not raw_urls:
        print(
            "ERROR: X_URLS is empty"
        )
        return 1

    urls = parse_urls(
        raw_urls
    )

    print(
        "UNIQUE X POSTS:",
        len(urls),
    )

    existing = load_existing_data()

    posts = []

    section(
        "FETCH X POSTS"
    )

    for index, item in enumerate(
        urls,
        start=1,
    ):
        print(
            f"Fetching {index}/{len(urls)}: "
            f"{item['post_id']}"
        )

        try:
            post = fetch_post(
                item
            )

            if post:
                posts.append(
                    post
                )

        except Exception as exc:
            print(
                "ERROR:",
                item["post_id"],
                exc,
            )

        if index < len(urls):
            time.sleep(
                REQUEST_INTERVAL
            )

    section(
        "MATCH RESULTS"
    )

    for index, post in enumerate(
        posts,
        start=1,
    ):
        candidates = find_candidates(
            post,
            existing,
        )

        print_result(
            index,
            len(posts),
            post,
            candidates,
        )

    section(
        "SUMMARY"
    )

    print(
        "INPUT UNIQUE POSTS:",
        len(urls),
    )

    print(
        "FETCHED POSTS:",
        len(posts),
    )

    print()
    print(
        "この診断では既存JSONへの"
        "書き込みは行っていません。"
    )

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )
