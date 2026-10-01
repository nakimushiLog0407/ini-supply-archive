#!/usr/bin/env python3

import html
import json
import math
import re
from urllib.parse import urlencode

import requests


# ============================================================
# テスト対象
# ============================================================

ORIGINAL_URL = (
    "https://x.com/official__ini/status/"
    "2104005920556736737"
)

TIMEOUT = 30


# ============================================================
# 共通
# ============================================================

def section(title):
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def extract_post_id(url):
    match = re.search(r"/status/(\d+)", url)

    if not match:
        raise ValueError("投稿IDをURLから取得できません")

    return match.group(1)


def normalize_url(url):
    return re.sub(
        r"https?://(?:www\.)?x\.com/",
        "https://twitter.com/",
        url,
        flags=re.IGNORECASE,
    )


def calculate_token(post_id):
    """
    Syndicationで使用されているtoken生成方式も試す。
    """
    value = (int(post_id) / 1e15) * math.pi

    token = (
        numpy_base36(value)
        .replace(".", "")
        .lstrip("0")
    )

    return token


def numpy_base36(number):
    """
    JavaScriptの Number(...).toString(36) に近い文字列を
    Pythonだけで生成する簡易実装。
    """

    chars = "0123456789abcdefghijklmnopqrstuvwxyz"

    integer = int(number)
    fraction = number - integer

    if integer == 0:
        integer_part = "0"
    else:
        result = []

        while integer:
            integer, remainder = divmod(integer, 36)
            result.append(chars[remainder])

        integer_part = "".join(reversed(result))

    if fraction == 0:
        return integer_part

    fraction_part = []

    for _ in range(16):
        fraction *= 36
        digit = int(fraction)
        fraction_part.append(chars[digit])
        fraction -= digit

        if fraction == 0:
            break

    return integer_part + "." + "".join(fraction_part)


def clean_html_text(raw_html):
    """
    oEmbedのHTMLから、診断用に見やすいテキストを取り出す。
    """

    text = re.sub(
        r"<script.*?</script>",
        "",
        raw_html,
        flags=re.DOTALL | re.IGNORECASE,
    )

    text = re.sub(
        r"<[^>]+>",
        " ",
        text,
    )

    text = html.unescape(text)

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    return text


# ============================================================
# oEmbed
# ============================================================

def test_oembed(normalized_url):
    section("TEST 1: oEmbed")

    endpoint = "https://publish.twitter.com/oembed"

    params = {
        "url": normalized_url,
        "omit_script": "true",
        "hide_thread": "true",
        "dnt": "true",
    }

    request_url = endpoint + "?" + urlencode(params)

    print("REQUEST:")
    print(request_url)

    try:
        response = requests.get(
            request_url,
            timeout=TIMEOUT,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(X11; Linux x86_64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/140.0.0.0 "
                    "Safari/537.36"
                )
            },
        )

        print()
        print("HTTP STATUS:", response.status_code)
        print("CONTENT-TYPE:", response.headers.get("content-type"))

        if response.status_code != 200:
            print()
            print("BODY:")
            print(response.text[:3000])
            return None

        data = response.json()

        print()
        print("JSON KEYS:")
        print(list(data.keys()))

        print()
        print("AUTHOR NAME:")
        print(data.get("author_name"))

        print()
        print("AUTHOR URL:")
        print(data.get("author_url"))

        print()
        print("RETURNED URL:")
        print(data.get("url"))

        raw_html = data.get("html", "")

        print()
        print("RAW HTML:")
        print(raw_html)

        print()
        print("CLEAN TEXT:")
        print(clean_html_text(raw_html))

        return data

    except Exception as exc:
        print()
        print("ERROR:")
        print(type(exc).__name__, str(exc))
        return None


# ============================================================
# Syndication
# ============================================================

def request_syndication(post_id, token, label):
    section(label)

    endpoint = "https://cdn.syndication.twimg.com/tweet-result"

    params = {
        "id": post_id,
        "lang": "ja",
        "token": token,
    }

    request_url = endpoint + "?" + urlencode(params)

    print("REQUEST:")
    print(request_url)

    try:
        response = requests.get(
            request_url,
            timeout=TIMEOUT,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(X11; Linux x86_64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/140.0.0.0 "
                    "Safari/537.36"
                )
            },
        )

        print()
        print("HTTP STATUS:", response.status_code)
        print("CONTENT-TYPE:", response.headers.get("content-type"))
        print("CONTENT-LENGTH:", len(response.content))

        print()
        print("RAW BODY:")
        print(response.text[:5000])

        if response.status_code != 200:
            return None

        try:
            data = response.json()
        except Exception as exc:
            print()
            print("JSON ERROR:", exc)
            return None

        if not data:
            print()
            print("RESULT: EMPTY JSON")
            return None

        print()
        print("JSON KEYS:")
        print(list(data.keys()))

        print()
        print("POST ID:")
        print(
            data.get("id_str")
            or data.get("id")
        )

        print()
        print("TEXT:")
        print(data.get("text"))

        print()
        print("CREATED AT:")
        print(data.get("created_at"))

        user = data.get("user") or {}

        print()
        print("USER NAME:")
        print(user.get("name"))

        print()
        print("SCREEN NAME:")
        print(user.get("screen_name"))

        photos = data.get("photos") or []

        print()
        print("PHOTO COUNT:")
        print(len(photos))

        media_details = data.get("mediaDetails") or []

        print()
        print("MEDIA DETAIL COUNT:")
        print(len(media_details))

        return data

    except Exception as exc:
        print()
        print("ERROR:")
        print(type(exc).__name__, str(exc))
        return None


# ============================================================
# 判定
# ============================================================

def evaluate(oembed, syndication_zero, syndication_calculated):
    section("FINAL RESULT")

    if oembed:
        print("oEmbed: SUCCESS")
    else:
        print("oEmbed: FAILED")

    if syndication_zero:
        print("Syndication token=0: SUCCESS")
    else:
        print("Syndication token=0: FAILED")

    if syndication_calculated:
        print("Syndication calculated token: SUCCESS")
    else:
        print("Syndication calculated token: FAILED")

    best = (
        syndication_calculated
        or syndication_zero
    )

    print()

    if best:
        print("STRUCTURED POST DATA: AVAILABLE")

        print()
        print("取得できた可能性のある情報:")

        print("- 投稿ID")
        print("- 本文")
        print("- 投稿日")
        print("- 投稿者")
        print("- メディア情報")

    elif oembed:
        print("OEMBED DATA ONLY: AVAILABLE")

        print()
        print(
            "本文・投稿者等は取得できていますが、"
            "構造化された投稿日やメディア情報については"
            "追加処理が必要です。"
        )

    else:
        print("POST DATA: NOT AVAILABLE")


# ============================================================
# main
# ============================================================

def main():
    section("X SINGLE POST DIAGNOSTIC")

    post_id = extract_post_id(
        ORIGINAL_URL
    )

    normalized_url = normalize_url(
        ORIGINAL_URL
    )

    calculated_token = calculate_token(
        post_id
    )

    print("ORIGINAL URL:")
    print(ORIGINAL_URL)

    print()
    print("NORMALIZED URL:")
    print(normalized_url)

    print()
    print("POST ID:")
    print(post_id)

    print()
    print("CALCULATED TOKEN:")
    print(calculated_token)

    oembed = test_oembed(
        normalized_url
    )

    syndication_zero = request_syndication(
        post_id,
        "0",
        "TEST 2: Syndication token=0",
    )

    syndication_calculated = request_syndication(
        post_id,
        calculated_token,
        "TEST 3: Syndication calculated token",
    )

    evaluate(
        oembed,
        syndication_zero,
        syndication_calculated,
    )

    section("DIAGNOSTIC FINISHED")

    print(
        "本番JSON・既存アプリへの変更は行っていません。"
    )


if __name__ == "__main__":
    main()
