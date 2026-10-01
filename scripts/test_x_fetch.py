#!/usr/bin/env python3

"""
X 公開投稿取得・診断スクリプト

目的:
    X公式API、有料API、ログイン情報を使用せず、
    GitHub Actions から公開状態のX投稿を
    どこまで取得できるか確認する。

対象:
    INI公式X
    @official__INI

重要:
    ・本番JSONは変更しない
    ・GitHubへの書き込みは行わない
    ・取得できた内容は標準出力へ表示するだけ
    ・診断専用
"""

from __future__ import annotations

import json
import re
import sys
import time
from html import unescape
from typing import Any

import requests


# ============================================================
# 設定
# ============================================================

USERNAME = "official__INI"

TIMEOUT = 20

USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
    "AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) "
    "Version/18.0 Mobile/15E148 Safari/604.1"
)


# ============================================================
# 共通
# ============================================================

def print_separator(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def make_session() -> requests.Session:
    session = requests.Session()

    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
    )

    return session


def request_url(
    session: requests.Session,
    url: str,
) -> requests.Response | None:

    print()
    print(f"GET: {url}")

    try:
        response = session.get(
            url,
            timeout=TIMEOUT,
            allow_redirects=True,
        )

        print(
            f"STATUS: {response.status_code}"
        )

        print(
            f"FINAL URL: {response.url}"
        )

        print(
            "CONTENT-TYPE:",
            response.headers.get(
                "content-type",
                "(なし)",
            ),
        )

        print(
            "CONTENT-LENGTH:",
            len(response.content),
        )

        return response

    except requests.RequestException as exc:
        print(
            f"REQUEST ERROR: {exc}"
        )

        return None


def shorten(
    value: Any,
    limit: int = 500,
) -> str:

    text = str(value)

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    if len(text) <= limit:
        return text

    return text[:limit] + " ..."


# ============================================================
# 診断1
# 通常のXプロフィールページ
# ============================================================

def test_profile_page(
    session: requests.Session,
) -> None:

    print_separator(
        "TEST 1: Xプロフィールページ"
    )

    url = (
        f"https://x.com/{USERNAME}"
    )

    response = request_url(
        session,
        url,
    )

    if response is None:
        return

    print()
    print("BODY PREVIEW:")
    print(
        shorten(
            response.text,
            1000,
        )
    )

    indicators = [
        USERNAME,
        "tweet",
        "timeline",
        "application/ld+json",
        "__NEXT_DATA__",
    ]

    print()
    print("INDICATORS:")

    lower_body = (
        response.text.lower()
    )

    for indicator in indicators:
        found = (
            indicator.lower()
            in lower_body
        )

        print(
            f"  {indicator}: "
            f"{'FOUND' if found else 'NOT FOUND'}"
        )


# ============================================================
# 診断2
# syndicationプロフィール
# ============================================================

def test_syndication_profile(
    session: requests.Session,
) -> None:

    print_separator(
        "TEST 2: syndication profile"
    )

    urls = [
        (
            "https://syndication.twitter.com/"
            f"srv/timeline-profile/screen-name/{USERNAME}"
        ),
        (
            "https://syndication.twitter.com/"
            f"timeline/profile?screen_name={USERNAME}"
        ),
    ]

    for url in urls:
        response = request_url(
            session,
            url,
        )

        if response is None:
            continue

        print()
        print("BODY PREVIEW:")
        print(
            shorten(
                response.text,
                1500,
            )
        )

        print()

        if USERNAME.lower() in (
            response.text.lower()
        ):
            print(
                "USERNAME: FOUND"
            )
        else:
            print(
                "USERNAME: NOT FOUND"
            )

        print()


# ============================================================
# 診断3
# syndication内部JSON候補の抽出
# ============================================================

def extract_json_candidates(
    html_text: str,
) -> list[Any]:

    candidates: list[Any] = []

    patterns = [
        (
            r'<script[^>]*'
            r'type=["\']application/json["\']'
            r'[^>]*>(.*?)</script>'
        ),
        r'<script[^>]*>(.*?)</script>',
    ]

    for pattern in patterns:
        matches = re.findall(
            pattern,
            html_text,
            flags=(
                re.IGNORECASE
                | re.DOTALL
            ),
        )

        for match in matches:
            raw = unescape(
                match.strip()
            )

            if not raw:
                continue

            if not (
                raw.startswith("{")
                or raw.startswith("[")
            ):
                continue

            try:
                parsed = json.loads(
                    raw
                )
            except json.JSONDecodeError:
                continue

            candidates.append(
                parsed
            )

    return candidates


def recursively_find_tweet_like_data(
    value: Any,
    results: list[dict[str, Any]],
) -> None:

    if isinstance(value, dict):

        keys = set(
            value.keys()
        )

        tweet_like_keys = {
            "id_str",
            "full_text",
            "text",
            "created_at",
            "screen_name",
        }

        if (
            keys
            & tweet_like_keys
        ):
            results.append(
                value
            )

        for child in value.values():
            recursively_find_tweet_like_data(
                child,
                results,
            )

    elif isinstance(value, list):

        for child in value:
            recursively_find_tweet_like_data(
                child,
                results,
            )


def test_syndication_json(
    session: requests.Session,
) -> None:

    print_separator(
        "TEST 3: syndication HTML内JSON解析"
    )

    url = (
        "https://syndication.twitter.com/"
        f"srv/timeline-profile/screen-name/{USERNAME}"
    )

    response = request_url(
        session,
        url,
    )

    if response is None:
        return

    if response.status_code != 200:
        print(
            "HTTP 200ではないため解析をスキップします。"
        )

        return

    candidates = (
        extract_json_candidates(
            response.text
        )
    )

    print()
    print(
        f"JSON CANDIDATES: {len(candidates)}"
    )

    tweet_like_data: list[
        dict[str, Any]
    ] = []

    for candidate in candidates:
        recursively_find_tweet_like_data(
            candidate,
            tweet_like_data,
        )

    print(
        "TWEET-LIKE OBJECTS:",
        len(tweet_like_data),
    )

    for index, item in enumerate(
        tweet_like_data[:20],
        start=1,
    ):
        print()
        print(
            f"--- OBJECT {index} ---"
        )

        for key in [
            "id",
            "id_str",
            "created_at",
            "screen_name",
            "name",
            "text",
            "full_text",
        ]:
            if key in item:
                print(
                    f"{key}: "
                    f"{shorten(item[key], 1000)}"
                )


# ============================================================
# 診断4
# HTML中のstatus URL探索
# ============================================================

def test_status_urls(
    session: requests.Session,
) -> None:

    print_separator(
        "TEST 4: status URL探索"
    )

    url = (
        "https://syndication.twitter.com/"
        f"srv/timeline-profile/screen-name/{USERNAME}"
    )

    response = request_url(
        session,
        url,
    )

    if response is None:
        return

    patterns = [
        (
            rf'https?://(?:x|twitter)\.com/'
            rf'{re.escape(USERNAME)}/status/(\d+)'
        ),
        r'/status/(\d+)',
    ]

    status_ids: list[str] = []

    for pattern in patterns:
        matches = re.findall(
            pattern,
            response.text,
            flags=re.IGNORECASE,
        )

        status_ids.extend(
            matches
        )

    status_ids = list(
        dict.fromkeys(
            status_ids
        )
    )

    print()
    print(
        f"STATUS IDS FOUND: {len(status_ids)}"
    )

    for status_id in status_ids[:30]:
        print(
            f"https://x.com/{USERNAME}/status/{status_id}"
        )


# ============================================================
# 診断5
# 既知の公開投稿をsyndicationで取得
# ============================================================

def test_known_tweet(
    session: requests.Session,
) -> None:

    print_separator(
        "TEST 5: 既知の公開投稿"
    )

    # 今回確認済みのINI公式Xの公開投稿。
    #
    # 投稿単体について、
    # ログインなしで情報取得できるか確認する。

    tweet_id = (
        "2104005920556736737"
    )

    urls = [
        (
            "https://cdn.syndication.twimg.com/"
            f"tweet-result?id={tweet_id}&lang=ja"
        ),
        (
            "https://syndication.twitter.com/"
            f"tweet-result?id={tweet_id}&lang=ja"
        ),
    ]

    for url in urls:

        response = request_url(
            session,
            url,
        )

        if response is None:
            continue

        print()
        print("BODY PREVIEW:")

        print(
            shorten(
                response.text,
                3000,
            )
        )

        content_type = (
            response.headers.get(
                "content-type",
                ""
            )
        )

        if (
            "json"
            in content_type.lower()
        ):
            try:
                data = response.json()

                print()
                print(
                    "JSON PARSE: SUCCESS"
                )

                print(
                    json.dumps(
                        data,
                        ensure_ascii=False,
                        indent=2,
                    )[:10000]
                )

            except ValueError:
                print(
                    "JSON PARSE: FAILED"
                )


# ============================================================
# main
# ============================================================

def main() -> int:

    print_separator(
        "X PUBLIC FETCH DIAGNOSTIC"
    )

    print(
        f"TARGET: @{USERNAME}"
    )

    print(
        "API KEY: NOT USED"
    )

    print(
        "LOGIN: NOT USED"
    )

    print(
        "WRITE FILE: NO"
    )

    session = make_session()

    tests = [
        test_profile_page,
        test_syndication_profile,
        test_syndication_json,
        test_status_urls,
        test_known_tweet,
    ]

    for test in tests:

        try:
            test(
                session
            )

        except Exception as exc:
            # 1つの診断が失敗しても
            # 後続テストを続行する。

            print()
            print(
                f"TEST ERROR: "
                f"{type(exc).__name__}: {exc}"
            )

        time.sleep(1)

    print_separator(
        "DIAGNOSTIC FINISHED"
    )

    print(
        "このスクリプトは診断のみです。"
    )

    print(
        "GitHub上のJSONや既存データは変更していません。"
    )

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )
