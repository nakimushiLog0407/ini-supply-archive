#!/usr/bin/env python3

import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from zoneinfo import ZoneInfo

import requests


# ==========================================================
# 設定
# ==========================================================

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
    value = normalize_text(
        value
    )

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

    value = value.replace(
        "#",
        "",
    )

    value = value.replace(
        "＃",
        "",
    )

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
        ZoneInfo(
            "Asia/Tokyo"
        )
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
        value = item.get(
            key
        )

        if value:
            return str(
                value
            )

    return ""


# ==========================================================
# X投稿取得
# ==========================================================

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
        data.get(
            "created_at"
        )
    )

    user = (
        data.get("user")
        or {}
    )

    return {
        "post_id": (
            item["post_id"]
        ),
        "url": (
            item["url"]
        ),
        "text": (
            data.get("text")
            or ""
        ),
        "created_at_jst": (
            created
        ),
        "author": (
            user.get(
                "screen_name"
            )
        ),
    }


# ==========================================================
# メンバー抽出
# ==========================================================

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
                and alias_compact
                in compact
            ):
                result.append(
                    canonical
                )
                break

    return result


def extract_item_members(item):
    values = []

    for key in [
        "title",
        "member",
        "members",
        "detail",
        "detailText",
        "description",
    ]:
        value = item.get(
            key
        )

        if isinstance(
            value,
            list,
        ):
            values.extend(
                str(v)
                for v in value
            )

        elif value:
            values.append(
                str(value)
            )

    return extract_members(
        "\n".join(
            values
        )
    )


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

    year = (
        post_date.year
    )

    dates = []

    # ------------------------------------------------------
    # 2026.09.30
    # 2026/09/30
    # 2026年09月30日
    # ------------------------------------------------------

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
            date = datetime(
                int(
                    match.group(1)
                ),
                int(
                    match.group(2)
                ),
                int(
                    match.group(3)
                ),
            ).date()

            dates.append(
                date
            )

        except ValueError:
            pass

    # ------------------------------------------------------
    # 10月8日
    # ------------------------------------------------------

    for match in re.finditer(
        r"(?<!\d)"
        r"(\d{1,2})月"
        r"(\d{1,2})日",
        text,
    ):
        try:
            date = datetime(
                year,
                int(
                    match.group(1)
                ),
                int(
                    match.group(2)
                ),
            ).date()

            # 11〜12月の投稿から
            # 1〜2月の予定を告知した場合
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

    # ------------------------------------------------------
    # 260930
    # ------------------------------------------------------

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

    # ------------------------------------------------------
    # 9/30
    # ------------------------------------------------------

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
                int(
                    match.group(1)
                ),
                int(
                    match.group(2)
                ),
            ).date()

            dates.append(
                date
            )

        except ValueError:
            pass

    unique = []

    for date in dates:
        if date not in unique:
            unique.append(
                date
            )

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
                result.append(
                    value
                )

    return result


def extract_fc_title(
    text,
    detected_type,
):
    # ------------------------------------------------------
    # Member Diary
    #
    # 🔽柾哉です
    # ------------------------------------------------------

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

    # ------------------------------------------------------
    # Message
    #
    # 「INI Type Check vol.5」が公開されました
    # ------------------------------------------------------

    if (
        detected_type
        == "message"
    ):
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

    # ------------------------------------------------------
    # Staff Report
    # ------------------------------------------------------

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

    phrases = (
        extract_quoted_phrases(
            text
        )
    )

    if phrases:
        return phrases[0]

    return None


def extract_schedule_names(text):
    result = []

    # ------------------------------------------------------
    # 括弧で囲まれた番組名
    # ------------------------------------------------------

    for phrase in (
        extract_quoted_phrases(
            text
        )
    ):
        normalized_phrase = (
            normalize_text(
                phrase
            )
        )

        if (
            normalized_phrase
            and normalized_phrase
            not in result
        ):
            result.append(
                normalized_phrase
            )

    normalized = normalize_text(
        text
    )

    # ------------------------------------------------------
    # 今回確認できている代表的な番組・イベント
    #
    # 曲名だけの「ANTHEM」はここに入れない。
    # ------------------------------------------------------

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
            result.append(
                value
            )

    return result


# ==========================================================
# 動画/SNS照合用キーワード
# ==========================================================

def extract_video_keywords(text):
    normalized = normalize_text(
        text
    )

    result = []

    # ------------------------------------------------------
    # 引用符内
    # ------------------------------------------------------

    for phrase in (
        extract_quoted_phrases(
            text
        )
    ):
        phrase = normalize_text(
            phrase
        )

        if (
            len(
                compact_text(
                    phrase
                )
            )
            >= 3
            and phrase not in result
        ):
            result.append(
                phrase
            )

    # ------------------------------------------------------
    # ハッシュタグ
    # ------------------------------------------------------

    for hashtag in re.findall(
        r"[#＃]"
        r"([0-9A-Za-z_ぁ-んァ-ヶ一-龯髙﨑]+)",
        text,
    ):
        value = normalize_text(
            hashtag
        )

        # INIなど汎用すぎるものは除外
        if value in {
            "ini",
            "mini",
        }:
            continue

        if (
            len(
                compact_text(
                    value
                )
            )
            < 3
        ):
            continue

        if value not in result:
            result.append(
                value
            )

    # ------------------------------------------------------
    # 特徴的な本文
    # ------------------------------------------------------

    special_patterns = [
        "mvコメンタリー",
        "you know what to do",
        "hi roto",
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
            result.append(
                value
            )

    return result


# ==========================================================
# 投稿タイプ判定
# ==========================================================

def detect_post_type(text):
    normalized = normalize_text(
        text
    )

    # ------------------------------------------------------
    # 対象外
    # ------------------------------------------------------

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
            "reason": (
                "sales_or_merchandise"
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
    # YouTube / クロスプラットフォーム動画
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
    # X / SNS独自コンテンツ
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
# 類似度
# ==========================================================

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

    if (
        a in b
        or b in a
    ):
        return 0.95

    return SequenceMatcher(
        None,
        a,
        b,
    ).ratio()


# ==========================================================
# 日付距離
# ==========================================================

def date_distance(
    date_a,
    date_b,
):
    if (
        not date_a
        or not date_b
    ):
        return None

    return abs(
        (
            date_a
            - date_b
        ).days
    )


# ==========================================================
# Schedule候補の事前絞り込み
# ==========================================================

def filter_schedule_candidates(
    post,
    items,
    event_dates,
):
    post_date = (
        post["created_at_jst"].date()
        if post.get(
            "created_at_jst"
        )
        else None
    )

    # ------------------------------------------------------
    # 明示的な出演日がある場合
    #
    # まず完全一致日だけを見る。
    # これがv3の最重要変更点。
    # ------------------------------------------------------

    if event_dates:
        exact = [
            item
            for item in items
            if get_item_date(
                item
            ) in event_dates
        ]

        if exact:
            return (
                exact,
                "event_date_exact",
            )

        # 完全一致がない場合のみ±1日
        near = []

        for item in items:
            item_date = (
                get_item_date(
                    item
                )
            )

            if not item_date:
                continue

            for event_date in (
                event_dates
            ):
                if (
                    date_distance(
                        item_date,
                        event_date,
                    )
                    <= 1
                ):
                    near.append(
                        item
                    )
                    break

        if near:
            return (
                near,
                "event_date_near",
            )

        # 日付が取れたのに該当Scheduleが
        # 見つからない場合、
        # 昔の同名番組へ飛ばさない。
        return (
            [],
            "event_date_no_match",
        )

    # ------------------------------------------------------
    # 出演日が本文にない場合
    #
    # 「出演しました」等は投稿日当日の出来事である
    # 可能性が高いため、投稿日を優先する。
    # ------------------------------------------------------

    if post_date:
        same_day = [
            item
            for item in items
            if get_item_date(
                item
            ) == post_date
        ]

        if same_day:
            return (
                same_day,
                "post_date_exact",
            )

        near = []

        for item in items:
            item_date = (
                get_item_date(
                    item
                )
            )

            if (
                item_date
                and date_distance(
                    item_date,
                    post_date,
                )
                <= 1
            ):
                near.append(
                    item
                )

        if near:
            return (
                near,
                "post_date_near",
            )

    # 日付が使えない場合のみ
    # 全Scheduleから探す。
    return (
        items,
        "no_date_filter",
    )


# ==========================================================
# FC候補の事前絞り込み
# ==========================================================

def filter_fc_candidates(
    post,
    items,
):
    post_date = (
        post["created_at_jst"].date()
        if post.get(
            "created_at_jst"
        )
        else None
    )

    if not post_date:
        return (
            items,
            "no_post_date",
        )

    # ------------------------------------------------------
    # 同日を最優先
    # ------------------------------------------------------

    same_day = [
        item
        for item in items
        if get_item_date(
            item
        ) == post_date
    ]

    if same_day:
        return (
            same_day,
            "publish_date_exact",
        )

    # ------------------------------------------------------
    # 同日がなければ±1日
    # ------------------------------------------------------

    near = []

    for item in items:
        item_date = (
            get_item_date(
                item
            )
        )

        if (
            item_date
            and date_distance(
                item_date,
                post_date,
            )
            <= 1
        ):
            near.append(
                item
            )

    if near:
        return (
            near,
            "publish_date_near",
        )

    # ------------------------------------------------------
    # 最新JSONに該当日のFCデータがない場合、
    # 古いタイトル類似だけで誤判定させない。
    # ------------------------------------------------------

    return (
        [],
        "publish_date_no_match",
    )


# ==========================================================
# YouTube候補の事前絞り込み
# ==========================================================

def filter_youtube_candidates(
    post,
    items,
):
    post_date = (
        post["created_at_jst"].date()
        if post.get(
            "created_at_jst"
        )
        else None
    )

    if not post_date:
        return (
            items,
            "no_post_date",
        )

    # ------------------------------------------------------
    # 投稿当日
    # ------------------------------------------------------

    same_day = [
        item
        for item in items
        if get_item_date(
            item
        ) == post_date
    ]

    if same_day:
        return (
            same_day,
            "publish_date_exact",
        )

    # ------------------------------------------------------
    # ±1日
    # ------------------------------------------------------

    near = []

    for item in items:
        item_date = (
            get_item_date(
                item
            )
        )

        if (
            item_date
            and date_distance(
                item_date,
                post_date,
            )
            <= 1
        ):
            near.append(
                item
            )

    if near:
        return (
            near,
            "publish_date_near",
        )

    # YouTubeはX告知と公開日に多少差が
    # 出る可能性があるため±3日まで拡張。
    wider = []

    for item in items:
        item_date = (
            get_item_date(
                item
            )
        )

        if (
            item_date
            and date_distance(
                item_date,
                post_date,
            )
            <= 3
        ):
            wider.append(
                item
            )

    if wider:
        return (
            wider,
            "publish_date_3days",
        )

    return (
        [],
        "publish_date_no_match",
    )


# ==========================================================
# Scheduleスコア
# ==========================================================

def score_schedule(
    post,
    item,
    event_dates,
    schedule_names,
    members,
    filter_reason,
):
    score = 0
    reasons = []

    item_date = (
        get_item_date(
            item
        )
    )

    item_title = (
        get_item_title(
            item
        )
    )

    # ------------------------------------------------------
    # 日付
    # ------------------------------------------------------

    if (
        event_dates
        and item_date
        in event_dates
    ):
        score += 100
        reasons.append(
            "event_date:exact"
        )

    elif (
        filter_reason
        == "event_date_near"
    ):
        score += 30
        reasons.append(
            "event_date:near"
        )

    elif (
        filter_reason
        == "post_date_exact"
    ):
        score += 60
        reasons.append(
            "post_date:exact"
        )

    elif (
        filter_reason
        == "post_date_near"
    ):
        score += 20
        reasons.append(
            "post_date:near"
        )

    # ------------------------------------------------------
    # 番組・イベント名
    # ------------------------------------------------------

    best_name = 0.0
    best_name_value = None

    for name in schedule_names:
        current = similarity(
            name,
            item_title,
        )

        if current > best_name:
            best_name = current
            best_name_value = name

    if best_name >= 0.90:
        score += 100
        reasons.append(
            "schedule_name:strong"
        )

    elif best_name >= 0.70:
        score += 65
        reasons.append(
            "schedule_name:medium"
        )

    elif best_name >= 0.50:
        score += 30
        reasons.append(
            "schedule_name:weak"
        )

    # ------------------------------------------------------
    # Listening Party特別処理
    #
    # ANTHEMではなく
    # Listening Party / STATIONHEAD をイベント識別に使う。
    # ------------------------------------------------------

    post_normalized = (
        normalize_text(
            post["text"]
        )
    )

    item_normalized = (
        normalize_text(
            item_title
            + "\n"
            + str(
                item.get(
                    "detailText",
                    ""
                )
            )
        )
    )

    listening_post = any(
        value in post_normalized
        for value in [
            "listening party",
            "stationhead",
            "ining_party",
        ]
    )

    listening_item = any(
        value in item_normalized
        for value in [
            "listening party",
            "stationhead",
            "ining_party",
        ]
    )

    if (
        listening_post
        and listening_item
    ):
        score += 120
        reasons.append(
            "event_identity:listening_party"
        )

    # ------------------------------------------------------
    # メンバー
    # ------------------------------------------------------

    item_members = set(
        extract_item_members(
            item
        )
    )

    common_members = (
        set(members)
        & item_members
    )

    if common_members:
        score += min(
            40,
            20
            * len(
                common_members
            ),
        )

        reasons.append(
            "member:"
            + ",".join(
                sorted(
                    common_members
                )
            )
        )

    return {
        "score": score,
        "reasons": reasons,
    }


# ==========================================================
# FCスコア
# ==========================================================

def score_fc(
    post,
    item,
    extracted_title,
    members,
    filter_reason,
):
    score = 0
    reasons = []

    item_title = (
        get_item_title(
            item
        )
    )

    # ------------------------------------------------------
    # 投稿日
    # ------------------------------------------------------

    if (
        filter_reason
        == "publish_date_exact"
    ):
        score += 80
        reasons.append(
            "publish_date:exact"
        )

    elif (
        filter_reason
        == "publish_date_near"
    ):
        score += 25
        reasons.append(
            "publish_date:near"
        )

    # ------------------------------------------------------
    # コンテンツタイトル
    # ------------------------------------------------------

    if extracted_title:
        title_score = similarity(
            extracted_title,
            item_title,
        )

        if title_score >= 0.95:
            score += 120
            reasons.append(
                "title:exact"
            )

        elif title_score >= 0.80:
            score += 90
            reasons.append(
                "title:strong"
            )

        elif title_score >= 0.60:
            score += 45
            reasons.append(
                "title:medium"
            )

    # ------------------------------------------------------
    # メンバー
    # ------------------------------------------------------

    item_members = set(
        extract_item_members(
            item
        )
    )

    common_members = (
        set(members)
        & item_members
    )

    if common_members:
        score += min(
            60,
            30
            * len(
                common_members
            ),
        )

        reasons.append(
            "member:"
            + ",".join(
                sorted(
                    common_members
                )
            )
        )

    return {
        "score": score,
        "reasons": reasons,
    }


# ==========================================================
# YouTubeスコア
# ==========================================================

def score_youtube(
    post,
    item,
    members,
    video_keywords,
    filter_reason,
):
    score = 0
    reasons = []

    item_title = (
        get_item_title(
            item
        )
    )

    item_normalized = (
        normalize_text(
            item_title
        )
    )

    # ------------------------------------------------------
    # 公開日
    # ------------------------------------------------------

    if (
        filter_reason
        == "publish_date_exact"
    ):
        score += 70
        reasons.append(
            "publish_date:exact"
        )

    elif (
        filter_reason
        == "publish_date_near"
    ):
        score += 30
        reasons.append(
            "publish_date:near"
        )

    elif (
        filter_reason
        == "publish_date_3days"
    ):
        score += 10
        reasons.append(
            "publish_date:3days"
        )

    # ------------------------------------------------------
    # 動画固有キーワード
    # ------------------------------------------------------

    keyword_hits = []

    for keyword in (
        video_keywords
    ):
        keyword_compact = (
            compact_text(
                keyword
            )
        )

        if (
            not keyword_compact
            or len(
                keyword_compact
            ) < 3
        ):
            continue

        item_compact = (
            compact_text(
                item_normalized
            )
        )

        if (
            keyword_compact
            in item_compact
        ):
            keyword_hits.append(
                keyword
            )

    if keyword_hits:
        score += min(
            120,
            45
            * len(
                keyword_hits
            ),
        )

        reasons.append(
            "video_keywords:"
            + ",".join(
                keyword_hits[:4]
            )
        )

    # ------------------------------------------------------
    # メンバー
    # ------------------------------------------------------

    item_members = set(
        extract_item_members(
            item
        )
    )

    common_members = (
        set(members)
        & item_members
    )

    if common_members:
        score += min(
            50,
            25
            * len(
                common_members
            ),
        )

        reasons.append(
            "member:"
            + ",".join(
                sorted(
                    common_members
                )
            )
        )

    return {
        "score": score,
        "reasons": reasons,
    }


# ==========================================================
# 候補検索
# ==========================================================

def find_matches(
    post,
    detected,
    datasets,
):
    detected_type = (
        detected["type"]
    )

    members = extract_members(
        post["text"]
    )

    event_dates = (
        extract_event_dates(
            post["text"],
            post[
                "created_at_jst"
            ],
        )
    )

    extracted_title = (
        extract_fc_title(
            post["text"],
            detected_type,
        )
    )

    schedule_names = (
        extract_schedule_names(
            post["text"]
        )
        if (
            detected_type
            == "schedule"
        )
        else []
    )

    video_keywords = (
        extract_video_keywords(
            post["text"]
        )
    )

    candidates = []

    # ------------------------------------------------------
    # Schedule
    # ------------------------------------------------------

    if (
        detected_type
        == "schedule"
    ):
        items, filter_reason = (
            filter_schedule_candidates(
                post,
                datasets.get(
                    "schedule",
                    [],
                ),
                event_dates,
            )
        )

        for item in items:
            match = score_schedule(
                post=post,
                item=item,
                event_dates=event_dates,
                schedule_names=schedule_names,
                members=members,
                filter_reason=(
                    filter_reason
                ),
            )

            if (
                match["score"]
                < 40
            ):
                continue

            candidates.append(
                make_candidate(
                    "schedule",
                    item,
                    match,
                    filter_reason,
                )
            )

    # ------------------------------------------------------
    # FC
    # ------------------------------------------------------

    elif detected_type in {
        "member_diary",
        "message",
        "movie",
        "photo",
        "radio",
    }:
        items, filter_reason = (
            filter_fc_candidates(
                post,
                datasets.get(
                    detected_type,
                    [],
                ),
            )
        )

        for item in items:
            match = score_fc(
                post=post,
                item=item,
                extracted_title=(
                    extracted_title
                ),
                members=members,
                filter_reason=(
                    filter_reason
                ),
            )

            if (
                match["score"]
                < 40
            ):
                continue

            candidates.append(
                make_candidate(
                    detected_type,
                    item,
                    match,
                    filter_reason,
                )
            )

    # ------------------------------------------------------
    # Video / SNS
    # ------------------------------------------------------

    elif detected_type in {
        "video",
        "sns",
    }:
        items, filter_reason = (
            filter_youtube_candidates(
                post,
                datasets.get(
                    "youtube",
                    [],
                ),
            )
        )

        for item in items:
            match = score_youtube(
                post=post,
                item=item,
                members=members,
                video_keywords=(
                    video_keywords
                ),
                filter_reason=(
                    filter_reason
                ),
            )

            # 日付だけ一致した動画を
            # 自動候補にしない。
            meaningful_reason = any(
                reason.startswith(
                    (
                        "video_keywords:",
                        "member:",
                    )
                )
                for reason in (
                    match[
                        "reasons"
                    ]
                )
            )

            if (
                match["score"]
                < 50
                or not meaningful_reason
            ):
                continue

            candidates.append(
                make_candidate(
                    "youtube",
                    item,
                    match,
                    filter_reason,
                )
            )

    candidates.sort(
        key=lambda item: (
            item["score"],
            item["date"] or "",
        ),
        reverse=True,
    )

    return candidates[:5]


def make_candidate(
    source_type,
    item,
    match,
    filter_reason,
):
    item_date = (
        get_item_date(
            item
        )
    )

    return {
        "source_type": (
            source_type
        ),
        "id": (
            item.get("id")
        ),
        "date": (
            item_date.isoformat()
            if item_date
            else None
        ),
        "title": (
            get_item_title(
                item
            )
        ),
        "url": (
            item.get("url")
        ),
        "score": (
            match["score"]
        ),
        "filter_reason": (
            filter_reason
        ),
        "reasons": (
            match["reasons"]
        ),
    }


# ==========================================================
# 最終分類
# ==========================================================

def classify_result(
    detected,
    matches,
):
    detected_type = (
        detected["type"]
    )

    # ------------------------------------------------------
    # 対象外
    # ------------------------------------------------------

    if (
        detected_type
        == "exclude"
    ):
        return (
            "exclude_candidate"
        )

    # ------------------------------------------------------
    # 未対応FC
    # ------------------------------------------------------

    if (
        detected_type
        == "staff_report"
    ):
        return (
            "unsupported_fc_content"
        )

    if (
        detected_type
        == "fc_unknown"
    ):
        return (
            "review_required"
        )

    # ------------------------------------------------------
    # Schedule
    # ------------------------------------------------------

    if (
        detected_type
        == "schedule"
    ):
        if matches:
            top = matches[0]

            # 日付＋番組名等で十分な根拠がある
            if (
                top["score"]
                >= 100
            ):
                return (
                    "existing_content_candidate"
                )

        return (
            "new_schedule_candidate"
        )

    # ------------------------------------------------------
    # FC
    # ------------------------------------------------------

    if detected_type in {
        "member_diary",
        "message",
        "movie",
        "photo",
        "radio",
    }:
        if matches:
            top = matches[0]

            if (
                top["score"]
                >= 100
            ):
                return (
                    "existing_content_candidate"
                )

        return (
            "review_required"
        )

    # ------------------------------------------------------
    # Video / SNS
    # ------------------------------------------------------

    if detected_type in {
        "video",
        "sns",
    }:
        if matches:
            top = matches[0]

            if (
                top["score"]
                >= 100
            ):
                return (
                    "existing_content_candidate"
                )

        return (
            "x_content_candidate"
        )

    return (
        "review_required"
    )


# ==========================================================
# Listening Partyグループ判定
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
        (
            post[
                "created_at_jst"
            ].isoformat()
            if post.get(
                "created_at_jst"
            )
            else None
        ),
    )

    print()
    print("TEXT:")
    print(
        post["text"]
    )

    members = extract_members(
        post["text"]
    )

    event_dates = (
        extract_event_dates(
            post["text"],
            post[
                "created_at_jst"
            ],
        )
    )

    extracted_title = (
        extract_fc_title(
            post["text"],
            detected["type"],
        )
    )

    schedule_names = (
        extract_schedule_names(
            post["text"]
        )
        if (
            detected["type"]
            == "schedule"
        )
        else []
    )

    video_keywords = (
        extract_video_keywords(
            post["text"]
        )
        if detected["type"]
        in {
            "video",
            "sns",
        }
        else []
    )

    group_key = (
        detect_group_key(
            post,
            detected,
        )
    )

    result = classify_result(
        detected,
        matches,
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
        (
            ", ".join(
                members
            )
            if members
            else "(none)"
        ),
    )

    print(
        "EXTRACTED EVENT DATES:",
        (
            ", ".join(
                date.isoformat()
                for date
                in event_dates
            )
            if event_dates
            else "(none)"
        ),
    )

    print(
        "EXTRACTED SCHEDULE NAMES:",
        (
            " / ".join(
                schedule_names
            )
            if schedule_names
            else "(none)"
        ),
    )

    print(
        "VIDEO KEYWORDS:",
        (
            " / ".join(
                video_keywords
            )
            if video_keywords
            else "(none)"
        ),
    )

    print(
        "GROUP KEY:",
        (
            group_key
            or "(none)"
        ),
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
            f"SCORE="
            f"{match['score']}"
        )

        print(
            "      TYPE:",
            match[
                "source_type"
            ],
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
            "      FILTER:",
            match[
                "filter_reason"
            ],
        )

        print(
            "      REASONS:",
            ", ".join(
                match[
                    "reasons"
                ]
            ),
        )


# ==========================================================
# メイン
# ==========================================================

def main():
    section(
        "X TYPE-FIRST MATCH DIAGNOSTIC V3"
    )

    raw_urls = (
        os.environ.get(
            "X_URLS",
            "",
        ).strip()
    )

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

    # ------------------------------------------------------
    # JSON読込
    # ------------------------------------------------------

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

    # ------------------------------------------------------
    # X取得
    # ------------------------------------------------------

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
            f"{index}/"
            f"{len(urls)}: "
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

        if (
            index
            < len(urls)
        ):
            time.sleep(
                REQUEST_INTERVAL
            )

    # ------------------------------------------------------
    # 判定
    # ------------------------------------------------------

    section(
        "TYPE-FIRST MATCH RESULTS V3"
    )

    summary = {}

    group_summary = {}

    for index, post in enumerate(
        posts,
        start=1,
    ):
        detected = (
            detect_post_type(
                post["text"]
            )
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

        group_key = (
            detect_group_key(
                post,
                detected,
            )
        )

        if group_key:
            if (
                group_key
                not in group_summary
            ):
                group_summary[
                    group_key
                ] = []

            group_summary[
                group_key
            ].append(
                post["post_id"]
            )

        print_post_result(
            index=index,
            total=len(posts),
            post=post,
            detected=detected,
            matches=matches,
        )

    # ------------------------------------------------------
    # Summary
    # ------------------------------------------------------

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

    # ------------------------------------------------------
    # 同一イベントグループ
    # ------------------------------------------------------

    section(
        "GROUPED POSTS"
    )

    if not group_summary:
        print(
            "(none)"
        )

    else:
        for (
            group_key,
            post_ids,
        ) in sorted(
            group_summary.items()
        ):
            print(
                group_key
            )

            for post_id in post_ids:
                print(
                    "  -",
                    post_id,
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
