import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# ==========================================================
# 設定
# ==========================================================

BASE_URL = "https://ini-official.com"

LIST_URL = (
    "https://ini-official.com/"
    "schedule/list/2026/9/"
    "?cat=L_ALL,live02,live03,live04,"
    "live05,live06,live07,live08,live09"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/18.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept": (
        "text/html,"
        "application/xhtml+xml,"
        "application/xml;q=0.9,"
        "*/*;q=0.8"
    ),
    "Accept-Language": (
        "ja-JP,ja;q=0.9,"
        "en-US;q=0.8,en;q=0.7"
    ),
}

TIMEOUT = 30

# 詳細ページを大量に開かないための上限。
DETAIL_DIAGNOSIS_LIMIT = 5


# ==========================================================
# 共通
# ==========================================================

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


def fetch_html(url):
    print()
    print("=" * 100)
    print("GET")
    print(url)
    print("=" * 100)

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT,
        allow_redirects=True,
    )

    print(
        "status:",
        response.status_code,
    )

    print(
        "final url:",
        response.url,
    )

    print(
        "content-type:",
        response.headers.get(
            "content-type"
        ),
    )

    print(
        "encoding:",
        response.encoding,
    )

    print(
        "bytes:",
        len(response.content),
    )

    print(
        "redirect count:",
        len(response.history),
    )

    if response.history:
        print()
        print("[REDIRECT HISTORY]")

        for item in response.history:
            print(
                item.status_code,
                "->",
                item.headers.get(
                    "location"
                ),
            )

    response.raise_for_status()

    return response.text, response.url


# ==========================================================
# 基本情報
# ==========================================================

def print_page_basic_info(
    soup,
    label,
):
    print()
    print("=" * 100)
    print(label)
    print("=" * 100)

    if soup.title:
        print(
            "title:",
            clean_text(
                soup.title.get_text(
                    " ",
                    strip=True,
                )
            ),
        )
    else:
        print(
            "title: (なし)"
        )

    h1_elements = soup.find_all(
        "h1"
    )

    print(
        "h1 count:",
        len(h1_elements),
    )

    for index, element in enumerate(
        h1_elements,
        start=1,
    ):
        print(
            f"h1 #{index}:",
            repr(
                clean_text(
                    element.get_text(
                        " ",
                        strip=True,
                    )
                )
            ),
        )


# ==========================================================
# Schedule関連class名
# ==========================================================

def diagnose_class_names(soup):
    print()
    print("=" * 100)
    print("SCHEDULE-RELATED CLASS NAMES")
    print("=" * 100)

    class_names = set()

    keywords = (
        "schedule",
        "list",
        "date",
        "day",
        "category",
        "cat",
        "title",
        "tit",
        "time",
        "member",
        "media",
        "live",
    )

    for element in soup.find_all(
        class_=True
    ):
        classes = element.get(
            "class",
            [],
        )

        for class_name in classes:
            lower_name = (
                class_name.lower()
            )

            if any(
                keyword in lower_name
                for keyword in keywords
            ):
                class_names.add(
                    class_name
                )

    print(
        "count:",
        len(class_names),
    )

    for class_name in sorted(
        class_names
    ):
        print(
            class_name
        )


# ==========================================================
# 日付候補
# ==========================================================

def diagnose_dates(soup):
    print()
    print("=" * 100)
    print("DATE CANDIDATES")
    print("=" * 100)

    patterns = [
        re.compile(
            r"\b20\d{2}[./-]\d{1,2}[./-]\d{1,2}\b"
        ),
        re.compile(
            r"\b\d{1,2}[./-]\d{1,2}\b"
        ),
        re.compile(
            r"\b\d{1,2}月\d{1,2}日\b"
        ),
    ]

    results = []

    for text_node in soup.stripped_strings:
        text = clean_text(
            text_node
        )

        if any(
            pattern.search(text)
            for pattern in patterns
        ):
            results.append(
                text
            )

    results = list(
        dict.fromkeys(
            results
        )
    )

    print(
        "count:",
        len(results),
    )

    for value in results:
        print(
            repr(value)
        )


# ==========================================================
# Scheduleカテゴリ候補
# ==========================================================

def diagnose_categories(soup):
    print()
    print("=" * 100)
    print("CATEGORY TEXT CANDIDATES")
    print("=" * 100)

    category_words = [
        "Release",
        "Live",
        "Event",
        "TV",
        "Radio",
        "Magazine",
        "Web",
        "Media",
        "Birthday",
        "Other",
        "リリース",
        "ライブ",
        "イベント",
        "テレビ",
        "ラジオ",
        "雑誌",
        "ウェブ",
        "誕生日",
        "その他",
    ]

    found = []

    for text_node in soup.stripped_strings:
        text = clean_text(
            text_node
        )

        lower_text = (
            text.lower()
        )

        if any(
            word.lower() in lower_text
            for word in category_words
        ):
            found.append(
                text
            )

    found = list(
        dict.fromkeys(
            found
        )
    )

    print(
        "count:",
        len(found),
    )

    for value in found:
        print(
            repr(value)
        )


# ==========================================================
# Scheduleリンク候補
# ==========================================================

def find_schedule_link_candidates(
    soup,
    base_url,
):
    candidates = []

    seen = set()

    for index, link in enumerate(
        soup.find_all(
            "a",
            href=True,
        ),
        start=1,
    ):
        href = link.get(
            "href",
            "",
        )

        full_url = absolute_url(
            base_url,
            href,
        )

        if "/schedule/" not in full_url:
            continue

        text = clean_text(
            link.get_text(
                " ",
                strip=True,
            )
        )

        key = (
            full_url,
            text,
        )

        if key in seen:
            continue

        seen.add(
            key
        )

        candidates.append(
            {
                "index": index,
                "href": href,
                "url": full_url,
                "text": text,
                "element": link,
            }
        )

    return candidates


def diagnose_schedule_links(
    soup,
    base_url,
):
    print()
    print("=" * 100)
    print("SCHEDULE LINK CANDIDATES")
    print("=" * 100)

    candidates = (
        find_schedule_link_candidates(
            soup,
            base_url,
        )
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
        print("-" * 100)
        print(
            f"CANDIDATE #{number}"
        )
        print("-" * 100)

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
            "href:",
            candidate["href"],
        )

        print(
            "url:",
            candidate["url"],
        )

        link = (
            candidate["element"]
        )

        print()
        print("[A TAG]")

        preview = str(
            link
        )

        if len(preview) > 3000:
            preview = (
                preview[:3000]
                + "\n... [truncated]"
            )

        print(
            preview
        )

        parent = link

        for level in range(
            1,
            5,
        ):
            parent = (
                parent.parent
            )

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
                parent.get(
                    "class"
                ),
            )

            print(
                "id:",
                parent.get(
                    "id"
                ),
            )

            parent_text = (
                clean_text(
                    parent.get_text(
                        " ",
                        strip=True,
                    )
                )
            )

            print(
                "text:",
                repr(
                    parent_text[:1000]
                ),
            )

            parent_preview = str(
                parent
            )

            if (
                len(parent_preview)
                > 5000
            ):
                parent_preview = (
                    parent_preview[:5000]
                    + "\n... [truncated]"
                )

            print(
                "html:"
            )

            print(
                parent_preview
            )

    return candidates


# ==========================================================
# 一覧ページ内の主要コンテナ候補
# ==========================================================

def diagnose_main_containers(soup):
    print()
    print("=" * 100)
    print("MAIN CONTAINER CANDIDATES")
    print("=" * 100)

    selectors = [
        "main",
        "article",
        "[class*='schedule']",
        "[class*='Schedule']",
        "[id*='schedule']",
        "[id*='Schedule']",
    ]

    printed = set()
    count = 0

    for selector in selectors:
        elements = soup.select(
            selector
        )

        for element in elements:
            identifier = id(
                element
            )

            if identifier in printed:
                continue

            printed.add(
                identifier
            )

            text = clean_text(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            if not text:
                continue

            count += 1

            print()
            print("-" * 100)
            print(
                f"CONTAINER #{count}"
            )
            print("-" * 100)

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
                element.get(
                    "class"
                ),
            )

            print(
                "id:",
                element.get(
                    "id"
                ),
            )

            print(
                "text:",
                repr(
                    text[:2000]
                ),
            )

            preview = str(
                element
            )

            if len(preview) > 10000:
                preview = (
                    preview[:10000]
                    + "\n... [truncated]"
                )

            print()
            print(
                "html:"
            )

            print(
                preview
            )

    if count == 0:
        print(
            "(Schedule本文候補なし)"
        )


# ==========================================================
# data-* 属性
# ==========================================================

def diagnose_data_attributes(soup):
    print()
    print("=" * 100)
    print("DATA ATTRIBUTE CANDIDATES")
    print("=" * 100)

    count = 0

    for element in soup.find_all(
        True
    ):
        data_attrs = {
            key: value
            for key, value
            in element.attrs.items()
            if key.startswith(
                "data-"
            )
        }

        if not data_attrs:
            continue

        text = clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        combined = (
            " ".join(
                str(value)
                for value
                in data_attrs.values()
            )
            + " "
            + text
        ).lower()

        interesting_words = (
            "schedule",
            "date",
            "category",
            "cat",
            "live",
            "release",
            "radio",
            "tv",
            "media",
        )

        if not any(
            word in combined
            for word in interesting_words
        ):
            continue

        count += 1

        print()
        print(
            f"[DATA ELEMENT #{count}]"
        )

        print(
            "tag:",
            element.name,
        )

        print(
            "class:",
            element.get(
                "class"
            ),
        )

        print(
            "attributes:",
            data_attrs,
        )

        print(
            "text:",
            repr(
                text[:500]
            ),
        )

    if count == 0:
        print(
            "(該当data属性なし)"
        )


# ==========================================================
# 画像候補
# ==========================================================

def diagnose_images(
    soup,
    base_url,
    label,
):
    print()
    print("=" * 100)
    print(label)
    print("=" * 100)

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
                base_url,
                image.get(
                    "src"
                ),
            ),
        )

        print(
            "data-src:",
            absolute_url(
                base_url,
                image.get(
                    "data-src"
                ),
            ),
        )

        print(
            "data-original:",
            absolute_url(
                base_url,
                image.get(
                    "data-original"
                ),
            ),
        )

        print(
            "data-lazy:",
            absolute_url(
                base_url,
                image.get(
                    "data-lazy"
                ),
            ),
        )

        print(
            "data-lazy-src:",
            absolute_url(
                base_url,
                image.get(
                    "data-lazy-src"
                ),
            ),
        )

        print(
            "srcset:",
            image.get(
                "srcset"
            ),
        )

        print(
            "alt:",
            image.get(
                "alt"
            ),
        )

        print(
            "class:",
            image.get(
                "class"
            ),
        )

        print(
            "style:",
            image.get(
                "style"
            ),
        )


# ==========================================================
# background-image候補
# ==========================================================

def diagnose_background_images(
    soup,
    base_url,
):
    print()
    print("=" * 100)
    print("BACKGROUND IMAGE CANDIDATES")
    print("=" * 100)

    pattern = re.compile(
        r"""url\(\s*['"]?([^'")]+)['"]?\s*\)""",
        re.IGNORECASE,
    )

    count = 0

    for element in soup.find_all(
        style=True
    ):
        style = element.get(
            "style",
            "",
        )

        if (
            "background"
            not in style.lower()
        ):
            continue

        matches = pattern.findall(
            style
        )

        for image_url in matches:
            count += 1

            print()
            print(
                f"[BACKGROUND #{count}]"
            )

            print(
                "tag:",
                element.name,
            )

            print(
                "class:",
                element.get(
                    "class"
                ),
            )

            print(
                "url:",
                absolute_url(
                    base_url,
                    image_url,
                ),
            )

            print(
                "style:",
                style,
            )

    if count == 0:
        print(
            "(background-image候補なし)"
        )


# ==========================================================
# 詳細ページ候補判定
# ==========================================================

def is_detail_candidate(url):
    if not url:
        return False

    parsed_url = (
        url.split(
            "?",
            1,
        )[0]
        .split(
            "#",
            1,
        )[0]
        .rstrip("/")
    )

    # 月別一覧ページは除外
    if re.search(
        r"/schedule/list/"
        r"\d{4}/\d{1,2}$",
        parsed_url,
    ):
        return False

    # detailを含むScheduleページ
    if re.search(
        r"/schedule/.*/detail/",
        parsed_url,
        re.IGNORECASE,
    ):
        return True

    if re.search(
        r"/schedule/detail/",
        parsed_url,
        re.IGNORECASE,
    ):
        return True

    return False


# ==========================================================
# 詳細ページ診断
# ==========================================================

def diagnose_detail(
    url,
    number,
):
    print()
    print()
    print("#" * 100)
    print(
        f"DETAIL PAGE DIAGNOSIS #{number}"
    )
    print("#" * 100)

    html, final_url = (
        fetch_html(
            url
        )
    )

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    print_page_basic_info(
        soup,
        "DETAIL PAGE BASIC INFO",
    )


    # ------------------------------------------------------
    # OGP / Twitter Card
    # ------------------------------------------------------

    print()
    print("=" * 100)
    print("DETAIL META")
    print("=" * 100)

    meta_count = 0

    for meta in soup.find_all(
        "meta"
    ):
        property_name = (
            meta.get(
                "property"
            )
            or meta.get(
                "name"
            )
            or ""
        )

        if (
            property_name.startswith(
                "og:"
            )
            or property_name.startswith(
                "twitter:"
            )
            or property_name
            in {
                "description",
                "keywords",
            }
        ):
            meta_count += 1

            print(
                property_name,
                "=",
                meta.get(
                    "content"
                ),
            )

    if meta_count == 0:
        print(
            "(対象metaなし)"
        )


    # ------------------------------------------------------
    # 見出し
    # ------------------------------------------------------

    print()
    print("=" * 100)
    print("DETAIL HEADINGS")
    print("=" * 100)

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
                f"{tag_name} #{index}"
            )

            print(
                "text:",
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
                heading.get(
                    "class"
                ),
            )

            print(
                "id:",
                heading.get(
                    "id"
                ),
            )

    if heading_count == 0:
        print(
            "(見出しなし)"
        )


    # ------------------------------------------------------
    # 詳細本文候補
    # ------------------------------------------------------

    print()
    print("=" * 100)
    print("DETAIL CONTENT CANDIDATES")
    print("=" * 100)

    selectors = [
        "main",
        "article",
        "[class*='schedule']",
        "[class*='detail']",
        "[class*='content']",
        "[class*='body']",
    ]

    printed = set()
    content_count = 0

    for selector in selectors:
        elements = soup.select(
            selector
        )

        for element in elements:
            identifier = id(
                element
            )

            if identifier in printed:
                continue

            printed.add(
                identifier
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
            print("-" * 100)
            print(
                f"CONTENT #{content_count}"
            )
            print("-" * 100)

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
                element.get(
                    "class"
                ),
            )

            print(
                "id:",
                element.get(
                    "id"
                ),
            )

            print(
                "text:",
                repr(
                    text[:3000]
                ),
            )

            preview = str(
                element
            )

            if len(preview) > 12000:
                preview = (
                    preview[:12000]
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

    diagnose_dates(
        soup
    )

    diagnose_categories(
        soup
    )

    diagnose_images(
        soup,
        final_url,
        "DETAIL IMAGE CANDIDATES",
    )

    diagnose_background_images(
        soup,
        final_url,
    )


# ==========================================================
# 一覧ページ診断
# ==========================================================

def diagnose_list():
    html, final_url = (
        fetch_html(
            LIST_URL
        )
    )

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    print_page_basic_info(
        soup,
        "LIST PAGE BASIC INFO",
    )

    diagnose_class_names(
        soup
    )

    diagnose_dates(
        soup
    )

    diagnose_categories(
        soup
    )

    diagnose_data_attributes(
        soup
    )

    candidates = (
        diagnose_schedule_links(
            soup,
            final_url,
        )
    )

    diagnose_main_containers(
        soup
    )

    diagnose_images(
        soup,
        final_url,
        "LIST PAGE IMAGE CANDIDATES",
    )

    diagnose_background_images(
        soup,
        final_url,
    )


    # ======================================================
    # 詳細ページ候補抽出
    # ======================================================

    detail_urls = []

    seen_urls = set()

    for candidate in candidates:
        url = candidate[
            "url"
        ]

        if not is_detail_candidate(
            url
        ):
            continue

        normalized_url = (
            url.split(
                "#",
                1,
            )[0]
        )

        if (
            normalized_url
            in seen_urls
        ):
            continue

        seen_urls.add(
            normalized_url
        )

        detail_urls.append(
            normalized_url
        )


    print()
    print("=" * 100)
    print("DETAIL PAGE URL CANDIDATES")
    print("=" * 100)

    print(
        "count:",
        len(detail_urls),
    )

    for index, url in enumerate(
        detail_urls,
        start=1,
    ):
        print(
            f"{index}: {url}"
        )


    # ======================================================
    # 詳細ページを最大5件診断
    # ======================================================

    if not detail_urls:
        print()
        print(
            "詳細ページ候補は見つかりませんでした。"
        )

        print(
            "一覧ページだけで情報が完結している"
            "可能性があります。"
        )

        return


    diagnosis_targets = (
        detail_urls[
            :DETAIL_DIAGNOSIS_LIMIT
        ]
    )


    print()
    print(
        "詳細ページ診断件数:",
        len(diagnosis_targets),
    )


    for index, url in enumerate(
        diagnosis_targets,
        start=1,
    ):
        try:
            diagnose_detail(
                url,
                index,
            )

        except Exception as error:
            # 詳細ページ1件の取得失敗だけで
            # 診断全体を終了させない。
            print()
            print(
                "[DETAIL ERROR]"
            )

            print(
                "url:",
                url,
            )

            print(
                "error:",
                repr(error),
            )


# ==========================================================
# 実行
# ==========================================================

if __name__ == "__main__":
    print("=" * 100)
    print("INI Schedule HTML diagnosis")
    print("=" * 100)

    print(
        "Target:",
        LIST_URL,
    )

    print()

    diagnose_list()

    print()
    print("=" * 100)
    print("DIAGNOSIS FINISHED")
    print("=" * 100)
