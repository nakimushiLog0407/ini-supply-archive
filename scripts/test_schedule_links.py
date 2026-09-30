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
    absolute_url,
    clean_schedule_detail_text,
    clean_text,
    extract_external_links,
    fetch_html,
    find_detail_content,
    is_schedule_back_link,
    is_social_share_url,
)

from bs4 import BeautifulSoup


# ==========================================================
# テスト対象
#
# Schedule詳細ページを少数だけ確認する。
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
                "isBack": (
                    is_schedule_back_link(
                        href,
                        label,
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
# detailText末尾判定
# ==========================================================

def has_ui_text_at_end(text):
    if not text:
        return False

    lines = [
        line.strip()
        for line in text.split("\n")
        if line.strip()
    ]

    if not lines:
        return False

    last_line = (
        lines[-1]
        .strip()
        .lower()
    )

    return last_line in {
        "share",
        "back",
    }


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
        raw_detail_text,
    ) = find_detail_content(
        soup
    )

    cleaned_detail_text = (
        clean_schedule_detail_text(
            raw_detail_text
        )
    )

    print()
    print(
        "クリーニング前本文文字数:",
        len(raw_detail_text),
    )

    print(
        "クリーニング後本文文字数:",
        len(cleaned_detail_text),
    )


    # ======================================================
    # detailTextクリーニング前後を確認
    # ======================================================

    print()
    print("-" * 100)
    print(
        "detailText 末尾確認"
    )
    print("-" * 100)

    raw_lines = [
        line
        for line in raw_detail_text.split(
            "\n"
        )
        if line.strip()
    ]

    cleaned_lines = [
        line
        for line in cleaned_detail_text.split(
            "\n"
        )
        if line.strip()
    ]

    print()
    print(
        "クリーニング前・末尾最大5行:"
    )

    for line in raw_lines[-5:]:
        print(
            "  ",
            repr(line),
        )

    print()
    print(
        "クリーニング後・末尾最大5行:"
    )

    for line in cleaned_lines[-5:]:
        print(
            "  ",
            repr(line),
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

        print(
            "back判定:",
            item["isBack"],
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
    # externalLinks検証
    # ======================================================

    remaining_share_links = []
    remaining_back_links = []

    for item in saved_links:
        link_url = item.get(
            "url",
            "",
        )

        link_label = item.get(
            "label",
            "",
        )

        if is_social_share_url(
            link_url
        ):
            remaining_share_links.append(
                link_url
            )

        if is_schedule_back_link(
            link_url,
            link_label,
        ):
            remaining_back_links.append(
                link_url
            )


    print()
    print("-" * 100)
    print(
        "externalLinks 除外テスト"
    )
    print("-" * 100)

    links_ok = True

    if remaining_share_links:
        links_ok = False

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

    if remaining_back_links:
        links_ok = False

        print(
            "RESULT: NG"
        )

        print(
            "BackリンクがexternalLinksに"
            "残っています。"
        )

        for back_url in (
            remaining_back_links
        ):
            print(
                "  ",
                back_url,
            )

    if links_ok:
        print(
            "RESULT: OK"
        )

        print(
            "Facebook / X(Twitter) / LINE の"
            "共有URLとBackリンクは"
            "externalLinksに残っていません。"
        )


    # ======================================================
    # detailText検証
    # ======================================================

    print()
    print("-" * 100)
    print(
        "detailText SHARE / Back 除外テスト"
    )
    print("-" * 100)

    text_ok = True

    if has_ui_text_at_end(
        cleaned_detail_text
    ):
        text_ok = False

        print(
            "RESULT: NG"
        )

        print(
            "クリーニング後のdetailText末尾に"
            "SHAREまたはBackが残っています。"
        )

    else:
        print(
            "RESULT: OK"
        )

        print(
            "クリーニング後のdetailText末尾に"
            "SHARE / Back は残っていません。"
        )


    # ======================================================
    # このページの最終結果
    # ======================================================

    print()
    print("-" * 100)
    print(
        "ページ最終結果"
    )
    print("-" * 100)

    page_ok = (
        links_ok
        and text_ok
    )

    if page_ok:
        print(
            "RESULT: OK"
        )

    else:
        print(
            "RESULT: NG"
        )

    return page_ok


# ==========================================================
# 実行
# ==========================================================

def main():
    print("=" * 100)
    print(
        "INI Schedule data cleanup test"
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
            "externalLinksとdetailTextの"
            "不要な共有UI除外処理は"
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
