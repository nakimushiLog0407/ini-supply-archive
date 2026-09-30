import sys
from pathlib import Path
from urllib.parse import urlparse


# ==========================================================
# scripts/fetch_schedule.py を読み込めるようにする
# ==========================================================

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT_DIR),
    )


from scripts.fetch_schedule import (
    BASE_URL,
    absolute_url,
    clean_text,
    extract_external_links,
    fetch_html,
    find_detail_content,
    is_social_share_url,
)

from bs4 import BeautifulSoup


# ==========================================================
# テスト対象
#
# Schedule詳細ページを少数だけ確認する。
# ここでは既に存在を確認している詳細ページを使用。
# ==========================================================

TEST_URLS = [
    "https://ini-official.com/schedule/detail/4301",
    "https://ini-official.com/schedule/detail/4225",
    "https://ini-official.com/schedule/detail/4023",
]


# ==========================================================
# 共有サービス判定
#
# ログを読みやすくするための表示用。
# 本番の除外判定そのものは
# fetch_schedule.py の is_social_share_url() を使用する。
# ==========================================================

def identify_service(url):
    parsed = urlparse(
        url
    )

    host = (
        parsed.netloc
        .lower()
        .split(":")[0]
    )

    if (
        "facebook.com"
        in host
    ):
        return "Facebook"

    if (
        host == "twitter.com"
        or host.endswith(
            ".twitter.com"
        )
        or host == "x.com"
        or host.endswith(
            ".x.com"
        )
    ):
        return "X/Twitter"

    if (
        host == "line.me"
        or host.endswith(
            ".line.me"
        )
    ):
        return "LINE"

    return ""


# ==========================================================
# HTML上の全リンクを確認
#
# これは診断表示専用。
# JSONには保存しない。
# ==========================================================

def get_all_content_links(
    content_element,
    detail_url,
):
    links = []

    seen = set()

    for link in content_element.find_all(
        "a",
        href=True,
    ):
        href = absolute_url(
            detail_url,
            link.get(
                "href",
                "",
            ),
        )

        if not href:
            continue

        if href in seen:
            continue

        seen.add(
            href
        )

        label = clean_text(
            link.get_text(
                " ",
                strip=True,
            )
        )

        links.append(
            {
                "label": label,
                "url": href,
                "isShare": (
                    is_social_share_url(
                        href
                    )
                ),
                "service": (
                    identify_service(
                        href
                    )
                ),
            }
        )

    return links


# ==========================================================
# 1ページ診断
# ==========================================================

def test_detail_page(
    url,
    number,
):
    print()
    print("=" * 100)
    print(
        f"TEST #{number}"
    )
    print("=" * 100)

    print(
        "URL:",
        url,
    )

    html, final_url = (
        fetch_html(
            url
        )
    )

    print(
        "取得成功:",
        final_url,
    )

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    (
        content_element,
        detail_text,
    ) = find_detail_content(
        soup
    )

    print()
    print(
        "本文文字数:",
        len(detail_text),
    )


    # ======================================================
    # 本文コンテナ内に存在するリンク
    # ======================================================

    all_links = (
        get_all_content_links(
            content_element,
            final_url,
        )
    )

    print()
    print("-" * 100)
    print(
        "本文コンテナ内の全リンク"
    )
    print("-" * 100)

    print(
        "件数:",
        len(all_links),
    )

    for index, item in enumerate(
        all_links,
        start=1,
    ):
        print()

        print(
            f"[{index}]"
        )

        print(
            "label:",
            repr(
                item["label"]
            ),
        )

        print(
            "url:",
            item["url"],
        )

        print(
            "service:",
            item["service"]
            or "-"
        )

        print(
            "share判定:",
            item["isShare"],
        )


    # ======================================================
    # 本番コードで実際に保存されるexternalLinks
    # ======================================================

    saved_links = (
        extract_external_links(
            content_element,
            final_url,
        )
    )

    print()
    print("-" * 100)
    print(
        "externalLinks に保存されるリンク"
    )
    print("-" * 100)

    print(
        "件数:",
        len(saved_links),
    )

    if not saved_links:
        print(
            "(なし)"
        )

    for index, item in enumerate(
        saved_links,
        start=1,
    ):
        print()

        print(
            f"[{index}]"
        )

        print(
            "label:",
            repr(
                item.get(
                    "label",
                    "",
                )
            ),
        )

        print(
            "url:",
            item.get(
                "url",
                "",
            ),
        )


    # ======================================================
    # 共有リンクが残っていないか検証
    # ======================================================

    remaining_share_links = []

    for item in saved_links:
        link_url = item.get(
            "url",
            "",
        )

        if is_social_share_url(
            link_url
        ):
            remaining_share_links.append(
                link_url
            )


    print()
    print("-" * 100)
    print(
        "共有リンク除外テスト"
    )
    print("-" * 100)

    if remaining_share_links:
        print(
            "RESULT: NG"
        )

        print(
            "共有リンクがexternalLinksに"
            "残っています。"
        )

        for share_url in (
            remaining_share_links
        ):
            print(
                "  ",
                share_url,
            )

        return False


    print(
        "RESULT: OK"
    )

    print(
        "Facebook / X(Twitter) / LINE の"
        "共有URLはexternalLinksに"
        "残っていません。"
    )

    return True


# ==========================================================
# 実行
# ==========================================================

def main():
    print("=" * 100)
    print(
        "INI Schedule externalLinks test"
    )
    print("=" * 100)

    print()
    print(
        "このテストでは"
        "data/schedule.jsonを変更しません。"
    )

    print(
        "テスト対象:",
        len(TEST_URLS),
        "ページ",
    )


    results = []


    for index, url in enumerate(
        TEST_URLS,
        start=1,
    ):
        try:
            result = (
                test_detail_page(
                    url,
                    index,
                )
            )

            results.append(
                result
            )

        except Exception as error:
            print()
            print(
                "ERROR:"
            )

            print(
                "URL:",
                url,
            )

            print(
                "内容:",
                repr(error),
            )

            results.append(
                False
            )


    print()
    print("=" * 100)
    print(
        "FINAL RESULT"
    )
    print("=" * 100)

    success_count = sum(
        1
        for result in results
        if result
    )

    print(
        "成功:",
        success_count,
        "/",
        len(results),
    )


    if all(results):
        print()
        print(
            "ALL TESTS PASSED"
        )

        print(
            "共有リンク除外処理は"
            "正常に動作しています。"
        )

        return


    print()
    print(
        "TEST FAILED"
    )

    raise SystemExit(
        1
    )


if __name__ == "__main__":
    main()
