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


DATA_FILES = {
    "schedule": Path("data/schedule.json"),
    "youtube": Path("data/youtube.json"),
    "member_diary": Path("data/member_diary.json"),
    "message": Path("data/message.json"),
    "movie": Path("data/movie.json"),
    "photo": Path("data/photo.json"),
    "radio": Path("data/radio.json"),
}


MEMBER_ALIASES = {
    "池﨑理人": [
        "池﨑理人",
        "池崎理人",
        "理人",
        "RIHITO",
    ],
    "尾崎匠海": [
        "尾崎匠海",
        "匠海",
        "TAKUMI",
    ],
    "木村柾哉": [
        "木村柾哉",
        "柾哉",
        "MASAYA",
    ],
    "後藤威尊": [
        "後藤威尊",
        "威尊",
        "TAKERU",
    ],
    "佐野雄大": [
        "佐野雄大",
        "雄大",
        "YUDAI",
    ],
    "シュウ・フェンファン": [
        "シュウ・フェンファン",
        "許豊凡",
        "フェンファン",
        "FENGFAN",
    ],
    "髙塚大夢": [
        "髙塚大夢",
        "高塚大夢",
        "大夢",
        "HIROMU",
    ],
    "田島将吾": [
        "田島将吾",
        "将吾",
        "SHOGO",
    ],
    "西洸人": [
        "西洸人",
        "洸人",
        "HIROTO",
    ],
    "藤牧京介": [
        "藤牧京介",
        "京介",
        "KYOSUKE",
    ],
    "松田迅": [
        "松田迅",
        "迅",
        "JIN",
    ],
}


# --------------------------------------------------
# Utility
# --------------------------------------------------

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
        r"[\s　]+",
        " ",
        value,
    )

    return value.strip()


def compact_text(value):
    value = normalize_text(value)

    value = re.sub(
        r"[@#＃]",
        "",
        value,
    )

    value = re.sub(
        r"[^0-9a-zぁ-んァ-ヶ一-龯髙﨑]+",
        "",
        value,
    )

    return value


def clean_hashtag(value):
    if not value:
        return ""

    value = value.replace("#", "")
    value = value.replace("＃", "")

    return value.strip()


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

    for token in re.split(
        r"\s+",
        raw.strip(),
    ):
        if not token:
            continue

        item = normalize_x_url(
            token
        )

        if not item:
            continue

        if item["post_id"] in seen:
            continue

        seen.add(
            item["post_id"]
        )

        unique.append(
            item
        )

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


def load_json(path):
    try:
        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(
                file
            )

        if isinstance(
            data,
            list,
        ):
            return data

        return []

    except Exception as exc:
        print(
            f"WARNING: {path}: {exc}"
        )
        return []


def parse_date(value):
    if not value:
        return None

    match = re.search(
        r"(\d{4})-(\d{2})-(\d{2})",
        str(value),
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
    keys = [
        "date",
        "publishedAt",
        "published_at",
        "startDate",
        "start_date",
        "datetime",
    ]

    for key in keys:
        date = parse_date(
            item.get(key)
        )

        if date:
            return date

    return None


def get_item_title(item):
    keys = [
        "title",
        "name",
        "program",
        "programName",
        "program_name",
    ]

    for key in keys:
        value = item.get(key)

        if value:
            return str(value)

    return ""


# --------------------------------------------------
# X fetch
# --------------------------------------------------

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
        "author": user.get(
            "screen_name"
        ),
    }


# --------------------------------------------------
# Member extraction
# --------------------------------------------------

def extract_members(text):
    compact = compact_text(
        text
    )

    result = []

    for canonical, aliases in (
        MEMBER_ALIASES.items()
    ):
        for alias in aliases:
            alias_compact = (
                compact_text(
                    alias
                )
            )

            if (
                alias_compact
                and alias_compact in compact
            ):
                result.append(
                    canonical
                )
                break

    return result


# --------------------------------------------------
# Date extraction
# --------------------------------------------------

def extract_event_dates(
    text,
    post_datetime,
):
    if not post_datetime:
        return []

    post_date = (
        post_datetime.date()
    )

    year = post_date.year

    dates = []

    # 2026.09.30
    for match in re.finditer(
        r"\b(20\d{2})[./年]"
        r"(\d{1,2})[./月]"
        r"(\d{1,2})日?\b",
        text,
    ):
        try:
            date = datetime(
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)),
            ).date()

            dates.append(
                date
            )

        except ValueError:
            pass

    # 10月8日
    for match in re.finditer(
        r"(?<!\d)"
        r"(\d{1,2})月"
        r"(\d{1,2})日",
        text,
    ):
        try:
            date = datetime(
                year,
                int(match.group(1)),
                int(match.group(2)),
            ).date()

            # 年跨ぎ対策
            if (
                post_date.month >= 11
                and date.month <= 2
            ):
                date = datetime(
                    year + 1,
                    date.month,
                    date.day,
                ).date()

            dates.append(
                date
            )

        except ValueError:
            pass

    # 260930
    for match in re.finditer(
        r"(?<!\d)"
        r"(\d{2})(\d{2})(\d{2})"
        r"(?!\d)",
        text,
    ):
        yy = int(
            match.group(1)
        )

        mm = int(
            match.group(2)
        )

        dd = int(
            match.group(3)
        )

        try:
            date = datetime(
                2000 + yy,
                mm,
                dd,
            ).date()

            dates.append(
                date
            )

        except ValueError:
            pass

    # 9/30
    for match in re.finditer(
        r"(?<!\d)"
        r"(\d{1,2})/"
        r"(\d{1,2})"
        r"(?!\d)",
        text,
    ):
        try:
            date = datetime(
                year,
                int(match.group(1)),
                int(match.group(2)),
            ).date()

            dates.append(
                date
            )

        except ValueError:
            pass

    # 重複削除
    unique = []

    for date in dates:
        if date not in unique:
            unique.append(
                date
            )

    return unique


# --------------------------------------------------
# Content title extraction
# --------------------------------------------------

def extract_quoted_phrases(text):
    patterns = [
        r"「([^」]{1,100})」",
        r"『([^』]{1,100})』",
        r"'([^']{1,100})'",
        r'"([^"]{1,100})"',
    ]

    result = []

    for pattern in patterns:
        for value in re.findall(
            pattern,
            text,
        ):
            value = clean_hashtag(
                value.strip()
            )

            if (
                value
                and value not in result
            ):
                result.append(
                    value
                )

    return result


def extract_fc_title(
    text,
    detected_type,
):
    if detected_type == "member_diary":
        match = re.search(
            r"🔽\s*([^\n]+)",
            text,
        )

        if match:
            return (
                match.group(1)
                .strip()
            )

    if detected_type == "message":
        match = re.search(
            r"「([^」]+)」"
            r"が公開されました",
            text,
        )

        if match:
            return (
                match.group(1)
                .strip()
            )

    if detected_type == "staff_report":
        match = re.search(
            r"🔽\s*([^\n]+)",
            text,
        )

        if match:
            return (
                match.group(1)
                .strip()
            )

    phrases = extract_quoted_phrases(
        text
    )

    if phrases:
        return phrases[0]

    return None


def extract_schedule_names(text):
    result = []

    for phrase in extract_quoted_phrases(
        text
    ):
        if phrase not in result:
            result.append(
                phrase
            )

    normalized = normalize_text(
        text
    )

    known_patterns = [
        "dayday.",
        "dayday",
        "ミュージックライン",
        "listening party",
        "ining_party",
        "stationhead",
    ]

    for value in known_patterns:
        if value in normalized:
            if value not in result:
                result.append(
                    value
                )

    return result


# --------------------------------------------------
# Type detection
# --------------------------------------------------

def detect_post_type(text):
    normalized = normalize_text(
        text
    )

    compact = compact_text(
        text
    )

    # ------------------------------------------
    # Exclude
    # ------------------------------------------

    exclude_words = [
        "受注販売",
        "ご購入いただけます",
        "販売スタート",
        "販売開始",
    ]

    if any(
        word in normalized
        for word in exclude_words
    ):
        return {
            "type": "exclude",
            "reason": "sales_or_merchandise",
        }

    # ------------------------------------------
    # FC
    # ------------------------------------------

    if (
        "official fanclub"
        in normalized
    ):
        if (
            "member diary"
            in normalized
        ):
            return {
                "type": "member_diary",
                "reason": "fc_member_diary",
            }

        if (
            "staff report"
            in normalized
        ):
            return {
                "type": "staff_report",
                "reason": "fc_staff_report",
            }

        if (
            "[message]"
            in normalized
            or "［message］"
            in normalized
            or "type check"
            in normalized
        ):
            return {
                "type": "message",
                "reason": "fc_message",
            }

        if (
            "[movie]"
            in normalized
            or "［movie］"
            in normalized
        ):
            return {
                "type": "movie",
                "reason": "fc_movie",
            }

        if (
            "[photo]"
            in normalized
            or "［photo］"
            in normalized
        ):
            return {
                "type": "photo",
                "reason": "fc_photo",
            }

        if (
            "[radio]"
            in normalized
            or "［radio］"
            in normalized
        ):
            return {
                "type": "radio",
                "reason": "fc_radio",
            }

        return {
            "type": "fc_unknown",
            "reason": "fc_unknown",
        }

    # ------------------------------------------
    # Schedule
    # ------------------------------------------

    schedule_words = [
        "生出演",
        "出演が決定",
        "出演しました",
        "ボイス出演",
        "出演中",
        "nhk-fm",
        "日本テレビ",
        "フジテレビ",
        "テレビ朝日",
        "tbs",
        "テレビ東京",
        "stationhead",
        "listening party",
        "ining_party",
    ]

    if any(
        word in normalized
        for word in schedule_words
    ):
        return {
            "type": "schedule",
            "reason": "appearance_or_event",
        }

    # ------------------------------------------
    # YouTube / cross-platform video
    # ------------------------------------------

    video_words = [
        "shorts",
        "youtube",
        "mvコメンタリー",
    ]

    if any(
        word in normalized
        for word in video_words
    ):
        return {
            "type": "video",
            "reason": "video_content",
        }

    # ------------------------------------------
    # X / SNS content
    # ------------------------------------------

    sns_words = [
        "tiktok",
        "instagram reels",
        "reels up",
        "[📱]",
    ]

    if any(
        word in normalized
        for word in sns_words
    ):
        return {
            "type": "sns",
            "reason": "social_content",
        }

    return {
        "type": "unknown",
        "reason": "no_rule",
    }


# --------------------------------------------------
# Matching
# --------------------------------------------------

def similarity(a, b):
    a = compact_text(
        a
    )

    b = compact_text(
        b
    )

    if not a or not b:
        return 0.0

    if a == b:
        return 1.0

    if a in b or b in a:
        return 0.95

    return SequenceMatcher(
        None,
        a,
        b,
    ).ratio()


def get_candidate_files(
    detected_type,
):
    if detected_type == "schedule":
        return [
            "schedule",
        ]

    if detected_type == "member_diary":
        return [
            "member_diary",
        ]

    if detected_type == "message":
        return [
            "message",
        ]

    if detected_type == "movie":
        return [
            "movie",
        ]

    if detected_type == "photo":
        return [
            "photo",
        ]

    if detected_type == "radio":
        return [
            "radio",
        ]

    if detected_type == "video":
        return [
            "youtube",
        ]

    if detected_type == "sns":
        # Shortsが含まれる場合などに
        # YouTubeとの関連を確認する。
        return [
            "youtube",
        ]

    return []


def calculate_match_score(
    post,
    item,
    detected_type,
    extracted_title,
    schedule_names,
    event_dates,
    members,
):
    score = 0
    reasons = []

    item_title = get_item_title(
        item
    )

    item_date = get_item_date(
        item
    )

    post_date = (
        post["created_at_jst"].date()
        if post.get("created_at_jst")
        else None
    )

    # ------------------------------------------
    # Exact / near title
    # ------------------------------------------

    if extracted_title:
        title_score = similarity(
            extracted_title,
            item_title,
        )

        if title_score >= 0.95:
            score += 70
            reasons.append(
                "title:exact"
            )

        elif title_score >= 0.80:
            score += 50
            reasons.append(
                "title:strong"
            )

        elif title_score >= 0.60:
            score += 25
            reasons.append(
                "title:medium"
            )

    # ------------------------------------------
    # Schedule program / event name
    # ------------------------------------------

    if detected_type == "schedule":
        best_name_score = 0

        for name in schedule_names:
            current = similarity(
                name,
                item_title,
            )

            best_name_score = max(
                best_name_score,
                current,
            )

        if best_name_score >= 0.90:
            score += 65
            reasons.append(
                "schedule_name:strong"
            )

        elif best_name_score >= 0.70:
            score += 40
            reasons.append(
                "schedule_name:medium"
            )

    # ------------------------------------------
    # Event date
    # ------------------------------------------

    if item_date and event_dates:
        if item_date in event_dates:
            score += 40
            reasons.append(
                "event_date:exact"
            )

        else:
            distance = min(
                abs(
                    (
                        item_date
                        - date
                    ).days
                )
                for date in event_dates
            )

            if distance == 1:
                score += 10
                reasons.append(
                    "event_date:near"
                )

    # ------------------------------------------
    # Publish date
    # FC / YouTube / SNSのみ強く使う
    # ------------------------------------------

    if (
        item_date
        and post_date
        and detected_type
        not in {
            "schedule",
        }
    ):
        difference = abs(
            (
                item_date
                - post_date
            ).days
        )

        if difference == 0:
            score += 30
            reasons.append(
                "publish_date:same"
            )

        elif difference == 1:
            score += 10
            reasons.append(
                "publish_date:near"
            )

    # ------------------------------------------
    # Member
    # ------------------------------------------

    item_member_text = " ".join(
        str(
            item.get(key) or ""
        )
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
            item_member_text
        )
    )

    common = (
        set(members)
        & item_members
    )

    if common:
        score += min(
            20,
            10 * len(common),
        )

        reasons.append(
            "member:"
            + ",".join(
                sorted(common)
            )
        )

    return {
        "score": score,
        "reasons": reasons,
    }


def find_matches(
    post,
    detected,
    datasets,
):
    detected_type = (
        detected["type"]
    )

    files = get_candidate_files(
        detected_type
    )

    if not files:
        return []

    members = extract_members(
        post["text"]
    )

    event_dates = extract_event_dates(
        post["text"],
        post["created_at_jst"],
    )

    extracted_title = extract_fc_title(
        post["text"],
        detected_type,
    )

    schedule_names = (
        extract_schedule_names(
            post["text"]
        )
        if detected_type == "schedule"
        else []
    )

    candidates = []

    for file_type in files:
        for item in datasets.get(
            file_type,
            [],
        ):
            match = (
                calculate_match_score(
                    post=post,
                    item=item,
                    detected_type=detected_type,
                    extracted_title=extracted_title,
                    schedule_names=schedule_names,
                    event_dates=event_dates,
                    members=members,
                )
            )

            if match["score"] < 30:
                continue

            candidates.append(
                {
                    "source_type": file_type,
                    "id": item.get("id"),
                    "date": (
                        get_item_date(
                            item
                        ).isoformat()
                        if get_item_date(
                            item
                        )
                        else None
                    ),
                    "title": get_item_title(
                        item
                    ),
                    "url": item.get(
                        "url"
                    ),
                    "score": match[
                        "score"
                    ],
                    "reasons": match[
                        "reasons"
                    ],
                }
            )

    candidates.sort(
        key=lambda x: x["score"],
        reverse=True,
    )

    return candidates[:5]


# --------------------------------------------------
# Result classification
# --------------------------------------------------

def classify_result(
    detected,
    matches,
):
    detected_type = (
        detected["type"]
    )

    if detected_type == "exclude":
        return "exclude_candidate"

    if detected_type == "staff_report":
        return (
            "unsupported_fc_content"
        )

    if detected_type == "fc_unknown":
        return (
            "review_required"
        )

    if matches:
        top = matches[0]

        if top["score"] >= 70:
            return (
                "existing_content_candidate"
            )

    if detected_type == "schedule":
        return (
            "new_schedule_candidate"
        )

    if detected_type in {
        "member_diary",
        "message",
        "movie",
        "photo",
        "radio",
    }:
        return (
            "review_required"
        )

    if detected_type in {
        "sns",
        "video",
    }:
        return (
            "x_content_candidate"
        )

    return "review_required"


# --------------------------------------------------
# Output
# --------------------------------------------------

def print_post_result(
    index,
    total,
    post,
    detected,
    matches,
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

    members = extract_members(
        post["text"]
    )

    event_dates = extract_event_dates(
        post["text"],
        post["created_at_jst"],
    )

    extracted_title = extract_fc_title(
        post["text"],
        detected["type"],
    )

    schedule_names = (
        extract_schedule_names(
            post["text"]
        )
        if detected["type"]
        == "schedule"
        else []
    )

    print()
    print(
        "DETECTED TYPE:",
        detected["type"],
    )

    print(
        "TYPE REASON:",
        detected["reason"],
    )

    print(
        "EXTRACTED TITLE:",
        extracted_title,
    )

    print(
        "EXTRACTED MEMBERS:",
        ", ".join(members)
        if members
        else "(none)",
    )

    print(
        "EXTRACTED EVENT DATES:",
        ", ".join(
            date.isoformat()
            for date in event_dates
        )
        if event_dates
        else "(none)",
    )

    print(
        "EXTRACTED SCHEDULE NAMES:",
        " / ".join(
            schedule_names
        )
        if schedule_names
        else "(none)",
    )

    result = classify_result(
        detected,
        matches,
    )

    print()
    print(
        "RESULT:",
        result,
    )

    print()
    print(
        "MATCH CANDIDATES:"
    )

    if not matches:
        print(
            "(none)"
        )
        return

    for number, match in enumerate(
        matches,
        start=1,
    ):
        print()
        print(
            f"  [{number}] "
            f"SCORE={match['score']}"
        )

        print(
            "      TYPE:",
            match["source_type"],
        )

        print(
            "      ID:",
            match["id"],
        )

        print(
            "      DATE:",
            match["date"],
        )

        print(
            "      TITLE:",
            match["title"],
        )

        print(
            "      REASONS:",
            ", ".join(
                match["reasons"]
            ),
        )


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():
    section(
        "X TYPE-FIRST MATCH DIAGNOSTIC"
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

    # ------------------------------------------
    # Load datasets
    # ------------------------------------------

    section(
        "LOAD DATASETS"
    )

    datasets = {}

    for name, path in (
        DATA_FILES.items()
    ):
        datasets[name] = (
            load_json(
                path
            )
        )

        print(
            f"{name}: "
            f"{len(datasets[name])}"
        )

    # ------------------------------------------
    # Fetch posts
    # ------------------------------------------

    section(
        "FETCH X POSTS"
    )

    posts = []

    for index, item in enumerate(
        urls,
        start=1,
    ):
        print(
            f"Fetching "
            f"{index}/{len(urls)}: "
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

    # ------------------------------------------
    # Analyze
    # ------------------------------------------

    section(
        "TYPE-FIRST MATCH RESULTS"
    )

    summary = {}

    for index, post in enumerate(
        posts,
        start=1,
    ):
        detected = detect_post_type(
            post["text"]
        )

        matches = find_matches(
            post,
            detected,
            datasets,
        )

        result = classify_result(
            detected,
            matches,
        )

        summary[result] = (
            summary.get(
                result,
                0,
            )
            + 1
        )

        print_post_result(
            index=index,
            total=len(posts),
            post=post,
            detected=detected,
            matches=matches,
        )

    # ------------------------------------------
    # Summary
    # ------------------------------------------

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

    for key in sorted(
        summary.keys()
    ):
        print(
            f"{key}: "
            f"{summary[key]}"
        )

    print()
    print(
        "No production data was modified."
    )

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )
