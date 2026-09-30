import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# ==========================================================
# 設定
# ==========================================================

LIST_URL = "https://ini-official.com/photo/list/4"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/18.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
}

TIMEOUT = 30


# ==========================================================
# 共通
# ==========================================================

def fetch_html(url):
    print()
    print("=" * 80)
    print("GET")
    print(url)
    print("=" * 80)

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT,
    )

    print("status:", response.status_code)
    print("final url:", response.url)
    print("content-type:", response.headers.get("content-type"))
    print("encoding:", response.encoding)
    print("bytes:", len(response.content))

    response.raise_for_status()

    return response.text


def clean_text(value):
    if not value:
        return ""

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


def absolute_url(base_url, value):
    if not value:
        return ""

    return urljoin(
        base_url,
        value,
    )


# ==========================================================
# 一覧ページ診断
# ==========================================================

def diagnose_list():
    html = fetch_html(LIST_URL)

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    print()
    print("=" * 80)
    print("PAGE TITLE")
    print("=" * 80)

    if soup.title:
        print(
            clean_text(
                soup.title.get_text(
                    " ",
                    strip=True,
                )
            )
        )
    else:
        print("(titleなし)")


    # ------------------------------------------------------
    # 一覧ページにあるMessage詳細リンク候補
    # ------------------------------------------------------

    print()
    print("=" * 80)
    print("MESSAGE DETAIL LINK CANDIDATES")
    print("=" * 80)

    candidates = []

    for index, link in enumerate(
        soup.find_all("a", href=True),
        start=1,
    ):
        href = link.get(
            "href",
            "",
        )

        full_url = absolute_url(
            LIST_URL,
            href,
        )

        text = clean_text(
            link.get_text(
                " ",
                strip=True,
            )
        )

        # /photo/ 以下だけを候補にする
        if "/photo/" not in full_url:
            continue

        # 一覧ページ自身は除外
        if (
            full_url.rstrip("/")
            == LIST_URL.rstrip("/")
        ):
            continue

        # /photo/list/数字 のような
        # 他カテゴリ一覧ページは除外
        if re.search(
            r"/photo/list/\d+/?$",
            full_url,
        ):
            continue

        candidates.append(
            {
                "index": index,
                "url": full_url,
                "text": text,
                "element": link,
            }
        )


    print(
        "candidate count:",
        len(candidates),
    )


    for number, candidate in enumerate(
        candidates,
        start=1,
    ):
        print()
        print("-" * 80)
        print(
            f"CANDIDATE #{number}"
        )
        print("-" * 80)

        print(
            "link index:",
            candidate["index"],
        )

        print(
            "text:",
            repr(
                candidate["text"]
            ),
        )

        print(
            "url:",
            candidate["url"],
        )

        link = candidate["element"]

        print()
        print("[A TAG]")
        print(
            link.prettify()
        )


        # --------------------------------------------------
        # 親要素を4階層まで確認
        # --------------------------------------------------

        parent = link

        for level in range(
            1,
            5,
        ):
            parent = parent.parent

            if parent is None:
                break

            print()
            print(
                f"[PARENT LEVEL {level}]"
            )

            print(
                "tag:",
                parent.name,
            )

            print(
                "class:",
                parent.get("class"),
            )

            print(
                "id:",
                parent.get("id"),
            )

            parent_text = clean_text(
                parent.get_text(
                    " ",
                    strip=True,
                )
            )

            print(
                "text:",
                repr(
                    parent_text[:500]
                ),
            )

            html_preview = str(
                parent
            )

            if (
                len(html_preview)
                > 3000
            ):
                html_preview = (
                    html_preview[:3000]
                    + "\n... [truncated]"
                )

            print("html:")
            print(
                html_preview
            )


    # ------------------------------------------------------
    # 日付らしい文字列
    # ------------------------------------------------------

    print()
    print("=" * 80)
    print("DATE TEXT CANDIDATES")
    print("=" * 80)

    date_pattern = re.compile(
        r"\b20\d{2}[./-]\d{1,2}[./-]\d{1,2}\b"
    )

    found_dates = []

    for text_node in soup.stripped_strings:
        text = clean_text(
            text_node
        )

        if date_pattern.search(
            text
        ):
            found_dates.append(
                text
            )


    unique_dates = list(
        dict.fromkeys(
            found_dates
        )
    )

    print(
        "date candidate count:",
        len(unique_dates),
    )

    for value in unique_dates:
        print(
            repr(value)
        )


    # ------------------------------------------------------
    # 一覧ページの画像候補
    # ------------------------------------------------------

    print()
    print("=" * 80)
    print("LIST PAGE IMAGE CANDIDATES")
    print("=" * 80)

    images = soup.find_all(
        "img"
    )

    print(
        "img count:",
        len(images),
    )


    for index, image in enumerate(
        images,
        start=1,
    ):
        print()
        print(
            f"[IMG #{index}]"
        )

        print(
            "src:",
            absolute_url(
                LIST_URL,
                image.get("src"),
            ),
        )

        print(
            "data-src:",
            absolute_url(
                LIST_URL,
                image.get("data-src"),
            ),
        )

        print(
            "data-original:",
            absolute_url(
                LIST_URL,
                image.get("data-original"),
            ),
        )

        print(
            "data-lazy:",
            absolute_url(
                LIST_URL,
                image.get("data-lazy"),
            ),
        )

        print(
            "data-lazy-src:",
            absolute_url(
                LIST_URL,
                image.get("data-lazy-src"),
            ),
        )

        print(
            "srcset:",
            image.get("srcset"),
        )

        print(
            "loading:",
            image.get("loading"),
        )

        print(
            "alt:",
            image.get("alt"),
        )

        print(
            "class:",
            image.get("class"),
        )


    # ------------------------------------------------------
    # 最初のMessage候補の詳細ページを診断
    # ------------------------------------------------------

    if not candidates:
        print()
        print(
            "Message詳細ページ候補が"
            "見つかりませんでした。"
        )

        return


    print()
    print("=" * 80)
    print("DETAIL PAGE DIAGNOSIS")
    print("=" * 80)

    first_detail_url = (
        candidates[0]["url"]
    )

    print(
        "diagnosis target:",
        first_detail_url,
    )

    diagnose_detail(
        first_detail_url
    )


# ==========================================================
# 詳細ページ診断
# ==========================================================

def diagnose_detail(url):
    html = fetch_html(
        url
    )

    soup = BeautifulSoup(
        html,
        "html.parser",
    )


    # ------------------------------------------------------
    # title
    # ------------------------------------------------------

    print()
    print("=" * 80)
    print("DETAIL PAGE TITLE")
    print("=" * 80)

    if soup.title:
        print(
            clean_text(
                soup.title.get_text(
                    " ",
                    strip=True,
                )
            )
        )
    else:
        print(
            "(titleなし)"
        )


    # ------------------------------------------------------
    # OGP / Twitter Card
    # ------------------------------------------------------

    print()
    print("=" * 80)
    print("OG META")
    print("=" * 80)

    meta_count = 0

    for meta in soup.find_all(
        "meta"
    ):
        property_name = (
            meta.get("property")
            or meta.get("name")
            or ""
        )

        if (
            property_name.startswith(
                "og:"
            )
            or property_name.startswith(
                "twitter:"
            )
        ):
            meta_count += 1

            print(
                property_name,
                "=",
                meta.get("content"),
            )


    if meta_count == 0:
        print(
            "(OGP/Twitter Cardなし)"
        )


    # ------------------------------------------------------
    # 見出し
    # ------------------------------------------------------

    print()
    print("=" * 80)
    print("HEADINGS")
    print("=" * 80)

    heading_count = 0

    for tag_name in [
        "h1",
        "h2",
        "h3",
        "h4",
    ]:
        for index, heading in enumerate(
            soup.find_all(
                tag_name
            ),
            start=1,
        ):
            heading_count += 1

            print()
            print(
                f"{tag_name} #{index}:",
                repr(
                    clean_text(
                        heading.get_text(
                            " ",
                            strip=True,
                        )
                    )
                ),
            )

            print(
                "class:",
                heading.get("class"),
            )

            print(
                "id:",
                heading.get("id"),
            )


    if heading_count == 0:
        print(
            "(見出しなし)"
        )


    # ------------------------------------------------------
    # 日付候補
    # ------------------------------------------------------

    print()
    print("=" * 80)
    print("DETAIL DATE CANDIDATES")
    print("=" * 80)

    date_pattern = re.compile(
        r"\b20\d{2}[./-]\d{1,2}[./-]\d{1,2}\b"
    )

    found_dates = []

    for text_node in soup.stripped_strings:
        text = clean_text(
            text_node
        )

        if date_pattern.search(
            text
        ):
            found_dates.append(
                text
            )


    unique_dates = list(
        dict.fromkeys(
            found_dates
        )
    )

    print(
        "date candidate count:",
        len(unique_dates),
    )

    for value in unique_dates:
        print(
            repr(value)
        )


    # ------------------------------------------------------
    # 詳細ページ画像
    # ------------------------------------------------------

    print()
    print("=" * 80)
    print("DETAIL IMAGE CANDIDATES")
    print("=" * 80)

    images = soup.find_all(
        "img"
    )

    print(
        "img count:",
        len(images),
    )


    for index, image in enumerate(
        images,
        start=1,
    ):
        print()
        print("-" * 80)
        print(
            f"IMG #{index}"
        )
        print("-" * 80)

        image_attributes = [
            "src",
            "data-src",
            "data-original",
            "data-lazy",
            "data-lazy-src",
            "srcset",
            "alt",
            "class",
            "id",
        ]

        url_attributes = {
            "src",
            "data-src",
            "data-original",
            "data-lazy",
            "data-lazy-src",
        }

        for attribute in (
            image_attributes
        ):
            value = image.get(
                attribute
            )

            if (
                attribute
                in url_attributes
            ):
                value = absolute_url(
                    url,
                    value,
                )

            print(
                f"{attribute}:",
                value,
            )


        # 親要素も確認
        parent = image.parent

        if parent is not None:
            print()
            print(
                "[IMAGE PARENT]"
            )

            print(
                "tag:",
                parent.name,
            )

            print(
                "class:",
                parent.get("class"),
            )

            print(
                "id:",
                parent.get("id"),
            )

            preview = str(
                parent
            )

            if (
                len(preview)
                > 2000
            ):
                preview = (
                    preview[:2000]
                    + "\n... [truncated]"
                )

            print(
                preview
            )


    # ------------------------------------------------------
    # CSS background-image候補
    # ------------------------------------------------------

    print()
    print("=" * 80)
    print("BACKGROUND IMAGE CANDIDATES")
    print("=" * 80)

    background_pattern = re.compile(
        r"""url\(['"]?([^'")]+)['"]?\)""",
        re.IGNORECASE,
    )

    background_count = 0

    for tag in soup.find_all(
        style=True
    ):
        style = tag.get(
            "style",
            "",
        )

        if (
            "background"
            not in style.lower()
        ):
            continue

        matches = (
            background_pattern.findall(
                style
            )
        )

        for image_url in matches:
            background_count += 1

            print()
            print(
                f"BACKGROUND #{background_count}"
            )

            print(
                "tag:",
                tag.name,
            )

            print(
                "class:",
                tag.get("class"),
            )

            print(
                "id:",
                tag.get("id"),
            )

            print(
                "url:",
                absolute_url(
                    url,
                    image_url,
                ),
            )

            print(
                "style:",
                style,
            )


    if background_count == 0:
        print(
            "(background-image候補なし)"
        )


    # ------------------------------------------------------
    # リンク候補
    # ------------------------------------------------------

    print()
    print("=" * 80)
    print("DETAIL LINKS")
    print("=" * 80)

    detail_links = soup.find_all(
        "a",
        href=True,
    )

    print(
        "link count:",
        len(detail_links),
    )


    for index, link in enumerate(
        detail_links,
        start=1,
    ):
        link_text = clean_text(
            link.get_text(
                " ",
                strip=True,
            )
        )

        link_url = absolute_url(
            url,
            link.get("href"),
        )

        print()
        print(
            f"LINK #{index}"
        )

        print(
            "text:",
            repr(link_text),
        )

        print(
            "url:",
            link_url,
        )

        print(
            "class:",
            link.get("class"),
        )


    # ------------------------------------------------------
    # main / article / Message関連のコンテナ候補
    # ------------------------------------------------------

    print()
    print("=" * 80)
    print("MAIN CONTENT CANDIDATES")
    print("=" * 80)

    selectors = [
        "main",
        "article",
        "[class*='photo']",
        "[class*='message']",
        "[class*='detail']",
        "[class*='content']",
    ]

    printed_elements = set()
    content_count = 0

    for selector in selectors:
        elements = soup.select(
            selector
        )

        for element in elements:
            element_identifier = id(
                element
            )

            if (
                element_identifier
                in printed_elements
            ):
                continue

            printed_elements.add(
                element_identifier
            )

            text = clean_text(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            if not text:
                continue

            content_count += 1

            print()
            print("-" * 80)

            print(
                f"CONTENT #{content_count}"
            )

            print(
                "selector:",
                selector,
            )

            print(
                "tag:",
                element.name,
            )

            print(
                "class:",
                element.get("class"),
            )

            print(
                "id:",
                element.get("id"),
            )

            print(
                "text:",
                repr(
                    text[:1000]
                ),
            )

            preview = str(
                element
            )

            if (
                len(preview)
                > 5000
            ):
                preview = (
                    preview[:5000]
                    + "\n... [truncated]"
                )

            print()
            print(
                "html:"
            )

            print(
                preview
            )


    if content_count == 0:
        print(
            "(本文候補なし)"
        )


# ==========================================================
# 実行
# ==========================================================

if __name__ == "__main__":
    print("=" * 80)
    print("INI Message HTML diagnosis")
    print("=" * 80)

    print(
        "List URL:",
        LIST_URL,
    )

    diagnose_list()

    print()
    print("=" * 80)
    print("DIAGNOSIS FINISHED")
    print("=" * 80)
