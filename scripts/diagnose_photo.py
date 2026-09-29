import re
import urllib.parse
import urllib.request
from html import unescape


# ============================================================
# 設定
# ============================================================

BASE_URL = "https://ini-official.com"

# FC PHOTOで使われている可能性のあるURLを順番に診断する。
# 404 / 403 / 405等になったURLも結果をログへ残す。
CANDIDATE_URLS = [
    f"{BASE_URL}/photo/",
    f"{BASE_URL}/photo/list/",
    f"{BASE_URL}/photos/",
    f"{BASE_URL}/photos/list/",
]

USER_AGENT = (
    "Mozilla/5.0 "
    "(Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/140.0.0.0 Safari/537.36"
)


# ============================================================
# HTML取得
# ============================================================

def fetch_html(url):

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": (
                "text/html,"
                "application/xhtml+xml,"
                "application/xml;q=0.9,"
                "*/*;q=0.8"
            ),
            "Accept-Language":
                "ja,en-US;q=0.9,en;q=0.8",
            "Cache-Control":
                "no-cache",
            "Pragma":
                "no-cache",
        },
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=30,
        ) as response:

            charset = (
                response.headers
                .get_content_charset()
                or "utf-8"
            )

            body = response.read()

            html = body.decode(
                charset,
                errors="replace",
            )

            return {
                "success": True,
                "status": response.status,
                "final_url": response.geturl(),
                "html": html,
            }

    except urllib.error.HTTPError as error:

        try:
            body = error.read().decode(
                "utf-8",
                errors="replace",
            )
        except Exception:
            body = ""

        return {
            "success": False,
            "status": error.code,
            "final_url": error.geturl(),
            "html": body,
        }

    except Exception as error:

        return {
            "success": False,
            "status": None,
            "final_url": url,
            "html": "",
            "error": str(error),
        }


# ============================================================
# HTMLタグを除去
# ============================================================

def strip_tags(value):

    value = re.sub(
        r"<script\b[^>]*>.*?</script>",
        " ",
        value,
        flags=(
            re.IGNORECASE |
            re.DOTALL
        ),
    )

    value = re.sub(
        r"<style\b[^>]*>.*?</style>",
        " ",
        value,
        flags=(
            re.IGNORECASE |
            re.DOTALL
        ),
    )

    value = re.sub(
        r"<[^>]+>",
        " ",
        value,
    )

    value = unescape(
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


# ============================================================
# ページタイトル取得
# ============================================================

def extract_title(page_html):

    match = re.search(
        r"<title\b[^>]*>(.*?)</title>",
        page_html,
        flags=(
            re.IGNORECASE |
            re.DOTALL
        ),
    )

    if not match:
        return None

    return strip_tags(
        match.group(1)
    )


# ============================================================
# リンク一覧
# ============================================================

def inspect_links(page_html):

    pattern = re.compile(
        r'<a\b[^>]*'
        r'href=["\']([^"\']+)["\']'
        r'[^>]*>',
        flags=re.IGNORECASE,
    )

    links = []

    for match in pattern.finditer(
        page_html
    ):

        raw_url = unescape(
            match.group(1)
        )

        absolute_url = (
            urllib.parse.urljoin(
                BASE_URL,
                raw_url,
            )
        )

        if absolute_url not in links:
            links.append(
                absolute_url
            )


    interesting = [
        url
        for url in links
        if (
            "photo" in url.lower()
            or
            "gallery" in url.lower()
            or
            "detail" in url.lower()
            or
            "fc" in url.lower()
        )
    ]


    print()
    print(
        "=" * 80
    )
    print(
        "INTERESTING LINKS"
    )
    print(
        "=" * 80
    )

    print(
        "all links:",
        len(links),
    )

    print(
        "interesting links:",
        len(interesting),
    )


    for url in interesting[
        :100
    ]:

        print(
            " ",
            url,
        )


# ============================================================
# imgタグ
# ============================================================

def inspect_images(page_html):

    image_tags = re.findall(
        r"<img\b[^>]*>",
        page_html,
        flags=re.IGNORECASE,
    )


    print()
    print(
        "=" * 80
    )
    print(
        "IMAGE DIAGNOSIS"
    )
    print(
        "=" * 80
    )

    print(
        "img tags:",
        len(image_tags),
    )


    for index, tag in enumerate(
        image_tags[:100],
        start=1,
    ):

        print()
        print(
            f"[IMG {index}]"
        )

        print(
            tag
        )


# ============================================================
# background-image
# ============================================================

def inspect_background_images(
    page_html
):

    pattern = re.compile(
        r'background(?:-image)?'
        r'\s*:\s*'
        r'url\(\s*'
        r'["\']?'
        r'([^)"\']+)'
        r'["\']?'
        r'\s*\)',
        flags=re.IGNORECASE,
    )


    urls = []

    for match in pattern.finditer(
        page_html
    ):

        raw_url = (
            match.group(1)
            .strip()
        )

        url = urllib.parse.urljoin(
            BASE_URL,
            raw_url,
        )

        if url not in urls:
            urls.append(
                url
            )


    print()
    print(
        "=" * 80
    )
    print(
        "BACKGROUND IMAGE DIAGNOSIS"
    )
    print(
        "=" * 80
    )

    print(
        "background images:",
        len(urls),
    )


    for index, url in enumerate(
        urls[:100],
        start=1,
    ):

        print(
            f"[{index}]",
            url,
        )


# ============================================================
# data-src / srcset 等
# ============================================================

def inspect_image_attributes(
    page_html
):

    patterns = {
        "data-src":
            r'data-src=["\']([^"\']+)["\']',

        "data-original":
            r'data-original=["\']([^"\']+)["\']',

        "srcset":
            r'srcset=["\']([^"\']+)["\']',

        "data-lazy":
            r'data-lazy=["\']([^"\']+)["\']',
    }


    print()
    print(
        "=" * 80
    )
    print(
        "LAZY IMAGE ATTRIBUTES"
    )
    print(
        "=" * 80
    )


    for label, pattern in (
        patterns.items()
    ):

        values = re.findall(
            pattern,
            page_html,
            flags=re.IGNORECASE,
        )

        unique_values = []

        for value in values:

            value = unescape(
                value
            )

            if value not in unique_values:
                unique_values.append(
                    value
                )


        print()
        print(
            f"{label}: "
            f"{len(unique_values)}件"
        )


        for value in unique_values[
            :50
        ]:

            print(
                " ",
                value,
            )


# ============================================================
# META画像
# ============================================================

def inspect_meta_images(
    page_html
):

    print()
    print(
        "=" * 80
    )
    print(
        "META IMAGE DIAGNOSIS"
    )
    print(
        "=" * 80
    )


    meta_tags = re.findall(
        r"<meta\b[^>]*>",
        page_html,
        flags=re.IGNORECASE,
    )


    found = 0


    for tag in meta_tags:

        lower = tag.lower()

        if (
            "og:image" in lower
            or
            "twitter:image" in lower
        ):

            found += 1

            print(
                tag
            )


    print(
        "image meta tags:",
        found,
    )


# ============================================================
# class一覧
# ============================================================

def inspect_classes(
    page_html
):

    class_values = re.findall(
        r'class=["\']([^"\']+)["\']',
        page_html,
        flags=re.IGNORECASE,
    )


    classes = set()


    for value in class_values:

        for class_name in (
            value.split()
        ):

            classes.add(
                class_name
            )


    interesting = sorted(
        class_name
        for class_name in classes
        if (
            "photo" in
            class_name.lower()

            or

            "gallery" in
            class_name.lower()

            or

            "thumb" in
            class_name.lower()

            or

            "title" in
            class_name.lower()

            or

            "date" in
            class_name.lower()

            or

            "list" in
            class_name.lower()

            or

            "item" in
            class_name.lower()
        )
    )


    print()
    print(
        "=" * 80
    )
    print(
        "CLASS DIAGNOSIS"
    )
    print(
        "=" * 80
    )

    print(
        "all unique classes:",
        len(classes),
    )

    print(
        "interesting classes:",
        len(interesting),
    )


    for class_name in interesting:

        print(
            " ",
            class_name,
        )


# ============================================================
# PHOTOという文字の周辺HTML
# ============================================================

def inspect_photo_keywords(
    page_html
):

    print()
    print(
        "=" * 80
    )
    print(
        "PHOTO KEYWORD CONTEXT"
    )
    print(
        "=" * 80
    )


    pattern = re.compile(
        r"photo",
        flags=re.IGNORECASE,
    )


    matches = list(
        pattern.finditer(
            page_html
        )
    )


    print(
        "PHOTO matches:",
        len(matches),
    )


    for index, match in enumerate(
        matches[:20],
        start=1,
    ):

        start = max(
            0,
            match.start() - 600,
        )

        end = min(
            len(page_html),
            match.end() + 1500,
        )


        print()
        print(
            "-" * 80
        )

        print(
            f"PHOTO CONTEXT {index}"
        )

        print(
            "-" * 80
        )

        print(
            page_html[
                start:end
            ]
        )


# ============================================================
# 日付候補
# ============================================================

def inspect_dates(
    page_html
):

    patterns = [
        r"\b20\d{2}\.\d{2}\.\d{2}\b",
        r"\b20\d{2}-\d{2}-\d{2}\b",
        r"\b20\d{2}/\d{2}/\d{2}\b",
    ]


    dates = []


    for pattern in patterns:

        for value in re.findall(
            pattern,
            page_html,
        ):

            if value not in dates:
                dates.append(
                    value
                )


    print()
    print(
        "=" * 80
    )
    print(
        "DATE DIAGNOSIS"
    )
    print(
        "=" * 80
    )

    print(
        "dates:",
        len(dates),
    )


    for value in dates[
        :100
    ]:

        print(
            " ",
            value,
        )


# ============================================================
# ページネーション
# ============================================================

def inspect_pagination(
    page_html
):

    page_links = re.findall(
        r'href=["\']'
        r'([^"\']*'
        r'[?&]page=\d+'
        r'[^"\']*)'
        r'["\']',
        page_html,
        flags=re.IGNORECASE,
    )


    unique_links = []


    for link in page_links:

        link = unescape(
            link
        )

        if link not in unique_links:

            unique_links.append(
                link
            )


    print()
    print(
        "=" * 80
    )
    print(
        "PAGINATION DIAGNOSIS"
    )
    print(
        "=" * 80
    )

    print(
        "pagination links:",
        len(unique_links),
    )


    for link in unique_links:

        print(
            " ",
            urllib.parse.urljoin(
                BASE_URL,
                link,
            ),
        )


# ============================================================
# 1ページ診断
# ============================================================

def diagnose_url(url):

    print()
    print()
    print(
        "#" * 80
    )

    print(
        "URL:",
        url,
    )

    print(
        "#" * 80
    )


    result = fetch_html(
        url
    )


    print(
        "HTTP status:",
        result.get(
            "status"
        ),
    )

    print(
        "Final URL:",
        result.get(
            "final_url"
        ),
    )


    if result.get(
        "error"
    ):

        print(
            "ERROR:",
            result[
                "error"
            ],
        )


    page_html = (
        result.get(
            "html"
        )
        or
        ""
    )


    print(
        "HTML length:",
        len(page_html),
    )


    if not page_html:

        print(
            "HTMLを取得できなかったため"
            "次のURLへ進みます。"
        )

        return


    page_title = (
        extract_title(
            page_html
        )
    )


    print(
        "PAGE TITLE:",
        page_title,
    )


    # HTML冒頭も少し表示
    print()
    print(
        "=" * 80
    )
    print(
        "HTML HEAD SAMPLE"
    )
    print(
        "=" * 80
    )

    print(
        page_html[:3000]
    )


    inspect_links(
        page_html
    )

    inspect_classes(
        page_html
    )

    inspect_images(
        page_html
    )

    inspect_background_images(
        page_html
    )

    inspect_image_attributes(
        page_html
    )

    inspect_meta_images(
        page_html
    )

    inspect_dates(
        page_html
    )

    inspect_pagination(
        page_html
    )

    inspect_photo_keywords(
        page_html
    )


# ============================================================
# メイン
# ============================================================

def main():

    print(
        "INI FC Photo HTML診断を開始します。"
    )

    print()
    print(
        "このスクリプトは診断専用です。"
    )

    print(
        "JSON・GitHub上のファイルは"
        "変更しません。"
    )


    for url in CANDIDATE_URLS:

        diagnose_url(
            url
        )


    print()
    print()
    print(
        "=" * 80
    )

    print(
        "診断完了"
    )

    print(
        "=" * 80
    )


if __name__ == "__main__":

    main()
