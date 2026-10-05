#!/usr/bin/env python3

import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

import requests


# ==========================================================
# 設定
# ==========================================================

TIMEOUT = 30
REQUEST_INTERVAL = 1.0

SYNDICATION_ENDPOINT = "https://cdn.syndication.twimg.com/tweet-result"

USER_AGENT = (
    "Mozilla/5.0 "
    "(X11; Linux x86_64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/140.0.0.0 "
    "Safari/537.36"
)

MEMBER_ALIASES = {
    "池﨑理人": ["池﨑理人", "池崎理人", "理人", "RIHITO"],
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

# ==========================================================
# 汎用
# ==========================================================

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
    ).lower()

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

    return (
        value
        .replace("#", "")
        .replace("＃", "")
        .strip()
    )


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
            f"{match.group(1)}/status/"
            f"{match.group(2)}"
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

        item = normalize_x_url(token)

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


def extract_media(data):
    media = []

    for item in (
        data.get("mediaDetails")
        or []
    ):
        if not isinstance(item, dict):
            continue

        media_type = item.get("type")
        original_info = (
            item.get("original_info")
            or {}
        )
        width = original_info.get("width")
        height = original_info.get("height")

        if media_type == "photo":
            url = item.get("media_url_https")

            if url:
                media.append({
                    "type": "photo",
                    "url": url,
                    "width": width,
                    "height": height,
                })

        elif media_type in {
            "video",
            "animated_gif",
        }:
            video_info = (
                item.get("video_info")
                or {}
            )
            mp4_variants = [
                variant
                for variant
                in (
                    video_info.get("variants")
                    or []
                )
                if (
                    isinstance(variant, dict)
                    and variant.get("content_type")
                    == "video/mp4"
                    and variant.get("url")
                )
            ]

            if not mp4_variants:
                continue

            best_variant = max(
                mp4_variants,
                key=lambda variant: (
                    variant.get("bitrate")
                    or 0
                ),
            )

            media.append({
                "type": "video",
                "thumbnailUrl": (
                    item.get("media_url_https")
                    or ""
                ),
                "videoUrl": best_variant["url"],
                "width": width,
                "height": height,
                "durationMillis": (
                    video_info.get("duration_millis")
                ),
            })

    return media


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

    user = (
        data.get("user")
        or {}
    )

    return {
        "post_id": item["post_id"],
        "url": item["url"],
        "text": (
            data.get("text")
            or ""
        ),
        "created_at_jst": created,
        "author": user.get(
            "screen_name"
        ),
        "media": extract_media(data),
    }


# ==========================================================
# メンバー抽出
# ==========================================================

def extract_members(text):
    compact = compact_text(text)

    result = []

    for canonical, aliases in (
        MEMBER_ALIASES.items()
    ):
        for alias in aliases:
            alias_compact = (
                compact_text(alias)
            )

            if (
                alias_compact
                and alias_compact
                in compact
            ):
                result.append(
                    canonical
                )
                break

    return result


# ==========================================================
# 日付抽出
# ==========================================================

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
    # 2026/09/30
    # 2026年09月30日
    for match in re.finditer(
        r"\b(20\d{2})"
        r"[./年]"
        r"(\d{1,2})"
        r"[./月]"
        r"(\d{1,2})"
        r"日?\b",
        text,
    ):
        try:
            dates.append(
                datetime(
                    int(match.group(1)),
                    int(match.group(2)),
                    int(match.group(3)),
                ).date()
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

            if (
                post_date.month >= 11
                and date.month <= 2
            ):
                date = datetime(
                    year + 1,
                    date.month,
                    date.day,
                ).date()

            dates.append(date)

        except ValueError:
            pass

    # 260930
    for match in re.finditer(
        r"(?<!\d)"
        r"(\d{2})(\d{2})(\d{2})"
        r"(?!\d)",
        text,
    ):
        try:
            dates.append(
                datetime(
                    2000
                    + int(
                        match.group(1)
                    ),
                    int(
                        match.group(2)
                    ),
                    int(
                        match.group(3)
                    ),
                ).date()
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
            dates.append(
                datetime(
                    year,
                    int(
                        match.group(1)
                    ),
                    int(
                        match.group(2)
                    ),
                ).date()
            )

        except ValueError:
            pass

    unique = []

    for date in dates:
        if date not in unique:
            unique.append(date)

    return unique


# ==========================================================
# タイトル・番組名抽出
# ==========================================================

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
                result.append(value)

    return result


def extract_fc_title(
    text,
    detected_type,
):
    if (
        detected_type
        == "member_diary"
    ):
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

    if (
        detected_type
        == "staff_report"
    ):
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
    """
    Scheduleの「固有名」候補を抽出する。

    v4では、曲名だけで別Scheduleに結び付かないようにする。
    Listening Party投稿の「ANTHEM」は作品名なので、
    Schedule固有名としては使用しない。
    """

    normalized = normalize_text(text)

    result = []

    known_patterns = [
        "dayday.",
        "dayday",
        "ミュージックライン",
        "listening party",
        "ining_party",
        "stationhead",
    ]

    for value in known_patterns:
        if (
            value in normalized
            and value not in result
        ):
            result.append(value)

    weak_work_names = {
        "anthem",
        "you know what to do",
    }

    for phrase in (
        extract_quoted_phrases(text)
    ):
        value = normalize_text(
            phrase
        )

        if value in weak_work_names:
            continue

        if (
            value
            and value not in result
        ):
            result.append(value)

    return result


# ==========================================================
# 動画/SNS照合用キーワード
# ==========================================================

def extract_video_keywords(text):
    normalized = normalize_text(text)

    result = []

    for phrase in (
        extract_quoted_phrases(text)
    ):
        phrase = normalize_text(
            phrase
        )

        if (
            len(
                compact_text(phrase)
            )
            >= 3
            and phrase not in result
        ):
            result.append(phrase)

    for hashtag in re.findall(
        r"[#＃]"
        r"([0-9A-Za-z_ぁ-んァ-ヶ一-龯髙﨑]+)",
        text,
    ):
        value = normalize_text(
            hashtag
        )

        if value in {
            "ini",
            "mini",
        }:
            continue

        if (
            len(
                compact_text(value)
            )
            < 3
        ):
            continue

        if value not in result:
            result.append(value)

    special_patterns = [
        "mvコメンタリー",
        "you know what to do",
        "hiroto",
        "befirst",
        "ryuhei",
        "見てるの気づいてるよ",
    ]

    for value in special_patterns:
        if (
            value in normalized
            and value not in result
        ):
            result.append(value)

    return result


def split_video_keywords(keywords):
    weak = []
    strong = []

    for keyword in keywords:
        normalized = normalize_text(
            keyword
        )

        if (
            normalized
            in WEAK_VIDEO_KEYWORDS
        ):
            weak.append(keyword)

        else:
            strong.append(keyword)

    return strong, weak


# ==========================================================
# 投稿タイプ判定
# ==========================================================

def detect_post_type(text):
    normalized = normalize_text(text)

    # ------------------------------------------------------
    # 対象外
    # ------------------------------------------------------

    sales_words = [
        "受注販売",
        "ご購入いただけます",
        "販売スタート",
        "販売開始",
    ]

    if any(
        word in normalized
        for word in sales_words
    ):
        return {
            "type": "exclude",
            "reason": (
                "sales_or_merchandise"
            ),
        }

    # サイト／FCそのものの開設告知は供給として記録しない。
    if (
        (
            "official site"
            in normalized
            or "official fanclub"
            in normalized
        )
        and any(
            word in normalized
            for word in [
                "open!",
                "open！",
                "オープン",
                "開設",
            ]
        )
    ):
        return {
            "type": "exclude",
            "reason": (
                "site_or_fanclub_open_notice"
            ),
        }

    # FC内のコンテンツが更新・公開されたことだけを知らせる
    # 告知投稿はX供給としては記録しない。
    # 個別のMember Diary等を示す投稿は、この一般通知より
    # 後段のFC判定に渡せるよう除外する。
    fc_content_labels = [
        "member diary",
        "staff report",
        "[message]",
        "［message］",
        "[movie]",
        "［movie］",
        "[photo]",
        "［photo］",
        "[radio]",
        "［radio］",
    ]

    is_specific_fc_content = any(
        label in normalized
        for label in fc_content_labels
    )

    if (
        "official fanclub"
        in normalized
        and not is_specific_fc_content
        and (
            "コンテンツ更新情報"
            in normalized
            or (
                "contents"
                in normalized
                and any(
                    word in normalized
                    for word in [
                        "公開されました",
                        "更新しました",
                        "更新情報",
                    ]
                )
            )
        )
    ):
        return {
            "type": "exclude",
            "reason": (
                "fanclub_content_update_notice"
            ),
        }

    # ------------------------------------------------------
    # FC
    # ------------------------------------------------------

    if (
        "official fanclub"
        in normalized
    ):
        if (
            "member diary"
            in normalized
        ):
            return {
                "type": (
                    "member_diary"
                ),
                "reason": (
                    "fc_member_diary"
                ),
            }

        if (
            "staff report"
            in normalized
        ):
            return {
                "type": (
                    "staff_report"
                ),
                "reason": (
                    "fc_staff_report"
                ),
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
                "reason": (
                    "fc_message"
                ),
            }

        if (
            "[movie]"
            in normalized
            or "［movie］"
            in normalized
        ):
            return {
                "type": "movie",
                "reason": (
                    "fc_movie"
                ),
            }

        if (
            "[photo]"
            in normalized
            or "［photo］"
            in normalized
        ):
            return {
                "type": "photo",
                "reason": (
                    "fc_photo"
                ),
            }

        if (
            "[radio]"
            in normalized
            or "［radio］"
            in normalized
        ):
            return {
                "type": "radio",
                "reason": (
                    "fc_radio"
                ),
            }

        return {
            "type": "fc_unknown",
            "reason": "fc_unknown",
        }

    # ------------------------------------------------------
    # Schedule
    # ------------------------------------------------------

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
            "reason": (
                "appearance_or_event"
            ),
        }

    # ------------------------------------------------------
    # YouTube
    # ------------------------------------------------------

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
            "reason": (
                "video_content"
            ),
        }

    # ------------------------------------------------------
    # SNS
    # ------------------------------------------------------

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
            "reason": (
                "social_content"
            ),
        }

    return {
        "type": "unknown",
        "reason": "no_rule",
    }


# ==========================================================
# グループ候補補助
# ==========================================================

def detect_group_key(
    post,
    detected,
):
    if (
        detected["type"]
        != "schedule"
    ):
        return None

    normalized = normalize_text(
        post["text"]
    )

    if any(
        value in normalized
        for value in [
            "listening party",
            "stationhead",
            "ining_party",
        ]
    ):
        post_date = (
            post[
                "created_at_jst"
            ].date()
            if post.get(
                "created_at_jst"
            )
            else None
        )

        if post_date:
            return (
                "listening_party:"
                + post_date.isoformat()
            )

        return (
            "listening_party"
        )

    return None


# ==========================================================
# 表示
# ==========================================================

def print_post_result(
    index,
    total,
    post,
    detected,
):
    section(
        f"POST {index}/{total}"
    )

    print("POST ID:", post["post_id"])
    print(
        "POSTED:",
        (
            post["created_at_jst"].isoformat()
            if post.get("created_at_jst")
            else None
        ),
    )
    print()
    print("TEXT:")
    print(post["text"])

    members = extract_members(post["text"])
    event_dates = extract_event_dates(
        post["text"],
        post["created_at_jst"],
    )
    extracted_title = extract_fc_title(
        post["text"],
        detected["type"],
    )
    group_key = detect_group_key(
        post,
        detected,
    )

    print()
    print("DETECTED TYPE:", detected["type"])
    print("TYPE REASON:", detected["reason"])
    print("EXTRACTED TITLE:", extracted_title)
    print(
        "EXTRACTED MEMBERS:",
        ", ".join(members) if members else "(none)",
    )
    print(
        "EXTRACTED EVENT DATES:",
        (
            ", ".join(
                date.isoformat()
                for date in event_dates
            )
            if event_dates
            else "(none)"
        ),
    )
    print("GROUP KEY:", group_key or "(none)")


def main():
    section("X POST ANALYSIS DIAGNOSTIC")

    raw_urls = os.environ.get(
        "X_URLS",
        "",
    ).strip()

    if not raw_urls:
        print("ERROR: X_URLS is empty")
        return 1

    urls = parse_urls(raw_urls)

    print("UNIQUE X POSTS:", len(urls))

    section("FETCH X POSTS")

    posts = []

    for index, item in enumerate(
        urls,
        start=1,
    ):
        print(
            f"Fetching {index}/"
            f"{len(urls)}: "
            f"{item['post_id']}"
        )

        try:
            post = fetch_post(item)

            if post:
                posts.append(post)

        except Exception as exc:
            print(
                "ERROR:",
                item["post_id"],
                exc,
            )

        if index < len(urls):
            time.sleep(REQUEST_INTERVAL)

    section("X POST ANALYSIS")

    summary = {}

    for index, post in enumerate(
        posts,
        start=1,
    ):
        detected = detect_post_type(
            post["text"]
        )

        key = detected["type"]
        summary[key] = (
            summary.get(key, 0) + 1
        )

        print_post_result(
            index=index,
            total=len(posts),
            post=post,
            detected=detected,
        )

    section("SUMMARY")
    print("INPUT UNIQUE POSTS:", len(urls))
    print("FETCHED POSTS:", len(posts))
    print()

    for key in sorted(summary):
        print(f"{key}: {summary[key]}")

    print()
    print("No production data was modified.")

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )
