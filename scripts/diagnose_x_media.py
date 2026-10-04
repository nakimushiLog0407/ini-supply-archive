#!/usr/bin/env python3

import json
from pprint import pprint

import requests


SYNDICATION_ENDPOINT = "https://cdn.syndication.twimg.com/tweet-result"

USER_AGENT = (
    "Mozilla/5.0 "
    "(X11; Linux x86_64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/140.0.0.0 "
    "Safari/537.36"
)

TIMEOUT = 30


TEST_POSTS = [
    {
        "label": "画像1枚",
        "post_id": "2105206011653230876",
    },
    {
        "label": "複数画像",
        "post_id": "2105190916898308519",
    },
    {
        "label": "動画",
        "post_id": "2105893039273328774",
    },
]


def fetch_post(post_id):
    response = requests.get(
        SYNDICATION_ENDPOINT,
        params={
            "id": post_id,
            "lang": "ja",
            "token": "0",
        },
        timeout=TIMEOUT,
        headers={
            "User-Agent": USER_AGENT,
        },
    )

    print(
        f"HTTP status: "
        f"{response.status_code}"
    )

    response.raise_for_status()

    return response.json()


def print_section(title):
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def inspect_media(data):
    """
    どのキーにメディア情報が入っているかを
    推測せず確認するため、候補となるキーを表示する。
    """

    print_section(
        "TOP LEVEL KEYS"
    )

    print(
        json.dumps(
            sorted(data.keys()),
            ensure_ascii=False,
            indent=2,
        )
    )


    print_section(
        "TEXT"
    )

    print(
        data.get("text", "")
    )


    print_section(
        "MEDIA-RELATED TOP LEVEL VALUES"
    )

    found = False

    for key, value in data.items():
        key_lower = key.lower()

        if any(
            word in key_lower
            for word in [
                "media",
                "photo",
                "video",
                "image",
                "card",
            ]
        ):
            found = True

            print()
            print(f"KEY: {key}")

            pprint(
                value,
                width=120,
                sort_dicts=False,
            )

    if not found:
        print(
            "メディア関連と思われる"
            "トップレベルキーは"
            "見つかりませんでした。"
        )


    print_section(
        "FULL RESPONSE"
    )

    print(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )


def main():
    print()
    print(
        "X Syndication Media Diagnosis"
    )

    print(
        "※ 診断専用です。"
        "ファイルへの保存・Git操作は行いません。"
    )


    for test in TEST_POSTS:
        print()
        print()
        print("#" * 80)
        print(
            f"# {test['label']}"
        )
        print(
            f"# Post ID: "
            f"{test['post_id']}"
        )
        print("#" * 80)

        try:
            data = fetch_post(
                test["post_id"]
            )

            if not data:
                print(
                    "レスポンスが空です。"
                )
                continue

            inspect_media(
                data
            )

        except Exception as exc:
            print()
            print(
                f"ERROR: {exc}"
            )


    print()
    print("=" * 80)
    print(
        "診断終了"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()
