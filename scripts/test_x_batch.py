#!/usr/bin/env python3

import json
import os
import re
import sys
import time
from datetime import datetime
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


def section(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def normalize_x_url(url):
    """
    ?s=46 などを除去し、投稿URLを正規化する。
    """

    url = url.strip()

    match = re.search(
        r"https?://(?:www\.)?(?:x|twitter)\.com/"
        r"([^/\s]+)/status/(\d+)",
        url,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    screen_name = match.group(1)
    post_id = match.group(2)

    return {
        "post_id": post_id,
        "screen_name_from_url": screen_name,
        "url": (
            f"https://x.com/"
            f"{screen_name}/status/{post_id}"
        ),
    }


def parse_input_urls(raw_text):
    """
    改行・空白区切りで渡されたURLを解析。
    投稿ID単位で重複を排除する。
    """

    tokens = re.split(r"\s+", raw_text.strip())

    valid = []
    invalid = []

    for token in tokens:
        if not token:
            continue

        parsed = normalize_x_url(token)

        if parsed:
            valid.append(parsed)
        else:
            invalid.append(token)

    unique = []
    duplicates = []
    seen_ids = set()

    for item in valid:
        post_id = item["post_id"]

        if post_id in seen_ids:
            duplicates.append(item)
            continue

        seen_ids.add(post_id)
        unique.append(item)

    return unique, duplicates, invalid


def convert_to_jst(created_at):
    """
    SyndicationのISO日時をJSTへ変換。
    """

    if not created_at:
        return None

    try:
        dt = datetime.fromisoformat(
            created_at.replace("Z", "+00:00")
        )

        jst = dt.astimezone(
            ZoneInfo("Asia/Tokyo")
        )

        return jst.isoformat()

    except Exception:
        return None


def extract_media(data):
    """
    Syndicationレスポンスから診断用メディア情報を抽出。
    """

    result = []

    photos = data.get("photos") or []

    for photo in photos:
        if not isinstance(photo, dict):
            continue

        result.append({
            "type": "photo",
            "url": (
                photo.get("url")
                or photo.get("media_url_https")
                or photo.get("media_url")
            ),
        })

    media_details = data.get("mediaDetails") or []

    for media in media_details:
        if not isinstance(media, dict):
            continue

        media_type = media.get("type")

        media_url = (
            media.get("media_url_https")
            or media.get("media_url")
        )

        item = {
            "type": media_type,
            "url": media_url,
        }

        if item not in result:
            result.append(item)

    return result


def fetch_post(item):
    """
    token=0 を使って単一投稿を取得する。
    前回の診断で成功した方式。
    """

    post_id = item["post_id"]

    params = {
        "id": post_id,
        "lang": "ja",
        "token": "0",
    }

    try:
        response = requests.get(
            SYNDICATION_ENDPOINT,
            params=params,
            timeout=TIMEOUT,
            headers={
                "User-Agent": USER_AGENT,
            },
        )

    except Exception as exc:
        return {
            "status": "error",
            "post_id": post_id,
            "url": item["url"],
            "error": (
                f"{type(exc).__name__}: {exc}"
            ),
        }

    if response.status_code != 200:
        return {
            "status": "error",
            "post_id": post_id,
            "url": item["url"],
            "http_status": response.status_code,
            "error": (
                f"HTTP {response.status_code}"
            ),
        }

    try:
        data = response.json()
    except Exception as exc:
        return {
            "status": "error",
            "post_id": post_id,
            "url": item["url"],
            "http_status": response.status_code,
            "error": (
                f"JSON parse error: {exc}"
            ),
        }

    if not data:
        return {
            "status": "empty",
            "post_id": post_id,
            "url": item["url"],
            "http_status": response.status_code,
        }

    user = data.get("user") or {}

    created_at_utc = data.get("created_at")
    created_at_jst = convert_to_jst(
        created_at_utc
    )

    text = data.get("text") or ""

    media = extract_media(data)

    return {
        "status": "success",
        "post_id": (
            data.get("id_str")
            or str(data.get("id") or post_id)
        ),
        "url": item["url"],
        "author_name": user.get("name"),
        "screen_name": user.get("screen_name"),
        "created_at_utc": created_at_utc,
        "created_at_jst": created_at_jst,
        "text": text,
        "media_count": len(media),
        "media": media,
    }


def print_post_result(index, total, result):
    section(
        f"POST {index}/{total}"
    )

    print(
        "STATUS:",
        result.get("status"),
    )

    print(
        "POST ID:",
        result.get("post_id"),
    )

    print(
        "URL:",
        result.get("url"),
    )

    if result.get("status") != "success":

        if result.get("http_status"):
            print(
                "HTTP STATUS:",
                result.get("http_status"),
            )

        if result.get("error"):
            print(
                "ERROR:",
                result.get("error"),
            )

        return

    print(
        "AUTHOR:",
        result.get("author_name"),
    )

    print(
        "SCREEN NAME:",
        result.get("screen_name"),
    )

    print(
        "CREATED AT UTC:",
        result.get("created_at_utc"),
    )

    print(
        "CREATED AT JST:",
        result.get("created_at_jst"),
    )

    print(
        "MEDIA COUNT:",
        result.get("media_count"),
    )

    print()
    print("TEXT:")
    print(
        result.get("text") or ""
    )


def print_summary(
    input_count,
    unique_count,
    duplicates,
    invalid,
    results,
):
    section("BATCH SUMMARY")

    success = [
        x for x in results
        if x.get("status") == "success"
    ]

    empty = [
        x for x in results
        if x.get("status") == "empty"
    ]

    errors = [
        x for x in results
        if x.get("status") == "error"
    ]

    print(
        "INPUT URL COUNT:",
        input_count,
    )

    print(
        "UNIQUE POST COUNT:",
        unique_count,
    )

    print(
        "DUPLICATE COUNT:",
        len(duplicates),
    )

    print(
        "INVALID COUNT:",
        len(invalid),
    )

    print(
        "SUCCESS COUNT:",
        len(success),
    )

    print(
        "EMPTY COUNT:",
        len(empty),
    )

    print(
        "ERROR COUNT:",
        len(errors),
    )

    if duplicates:

        print()
        print("DUPLICATES:")

        for item in duplicates:
            print(
                "-",
                item["post_id"],
                item["url"],
            )

    if invalid:

        print()
        print("INVALID INPUT:")

        for value in invalid:
            print(
                "-",
                value,
            )


def print_date_groups(results):
    """
    JST投稿日ごとにまとめて表示。
    """

    section("POSTS GROUPED BY JST DATE")

    groups = {}

    for result in results:

        if result.get("status") != "success":
            continue

        created = result.get("created_at_jst")

        if created:
            date = created[:10]
        else:
            date = "unknown"

        groups.setdefault(
            date,
            []
        ).append(result)

    for date in sorted(groups):

        print()
        print(
            f"[{date}] "
            f"{len(groups[date])} posts"
        )

        for result in groups[date]:

            text = (
                result.get("text")
                or ""
            )

            preview = re.sub(
                r"\s+",
                " ",
                text,
            ).strip()

            if len(preview) > 100:
                preview = (
                    preview[:100]
                    + "..."
                )

            print(
                "-",
                result.get("post_id"),
                "|",
                preview,
            )


def print_json_preview(results):
    """
    次の分類テストで扱いやすい形を確認するため、
    取得成功分をJSONとしてログへ表示。
    """

    section("NORMALIZED JSON PREVIEW")

    successful = [
        result
        for result in results
        if result.get("status") == "success"
    ]

    print(
        json.dumps(
            successful,
            ensure_ascii=False,
            indent=2,
        )
    )


def main():
    section("X BATCH FETCH DIAGNOSTIC")

    raw_urls = os.environ.get(
        "X_URLS",
        "",
    ).strip()

    if not raw_urls:
        print(
            "ERROR: X_URLS が空です。"
        )
        return 1

    raw_tokens = [
        token
        for token in re.split(
            r"\s+",
            raw_urls,
        )
        if token
    ]

    (
        unique,
        duplicates,
        invalid,
    ) = parse_input_urls(
        raw_urls
    )

    print(
        "INPUT URL COUNT:",
        len(raw_tokens),
    )

    print(
        "VALID UNIQUE COUNT:",
        len(unique),
    )

    print(
        "DUPLICATE COUNT:",
        len(duplicates),
    )

    print(
        "INVALID COUNT:",
        len(invalid),
    )

    if not unique:
        print(
            "取得対象の有効なX URLがありません。"
        )
        return 1

    results = []

    total = len(unique)

    for index, item in enumerate(
        unique,
        start=1,
    ):

        result = fetch_post(
            item
        )

        results.append(
            result
        )

        print_post_result(
            index,
            total,
            result,
        )

        if index < total:
            time.sleep(
                REQUEST_INTERVAL
            )

    print_summary(
        input_count=len(raw_tokens),
        unique_count=len(unique),
        duplicates=duplicates,
        invalid=invalid,
        results=results,
    )

    print_date_groups(
        results
    )

    print_json_preview(
        results
    )

    section("DIAGNOSTIC FINISHED")

    print(
        "本番JSON・既存アプリへの"
        "書き込みは行っていません。"
    )

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )
