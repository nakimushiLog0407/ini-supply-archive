import re
import urllib.parse
import urllib.request


# ============================================================
# 設定
# ============================================================

BASE_URL = "https://ini-official.com"

LIST_URL = (
    f"{BASE_URL}/blog/list/1/0/"
)

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

    with urllib.request.urlopen(
        request,
        timeout=30,
    ) as response:

        charset = (
            response.headers.get_content_charset()
            or "utf-8"
        )

        return response.read().decode(
            charset,
            errors="replace",
        )


# ============================================================
# URLを絶対URLへ
# ============================================================

def absolute_url(url):
    if not url:
        return None

    return urllib.parse.urljoin(
        BASE_URL,
        url.strip(),
    )


# ============================================================
# imgタグを解析
# ============================================================

def inspect_images(html):
    image_pattern = re.compile(
        r"<img\b[^>]*>",
        flags=re.IGNORECASE,
    )

    images = image_pattern.findall(
        html
    )

    print(
        f"imgタグ数: {len(images)}"
    )

    for index, tag in enumerate(
        images,
        start=1,
    ):

        print()
        print(
            f"--- IMG {index} ---"
        )

        print(tag)

        src_match = re.search(
            r'\bsrc=["\']([^"\']+)["\']',
            tag,
            flags=re.IGNORECASE,
        )

        data_src_match = re.search(
            r'\bdata-src=["\']([^"\']+)["\']',
            tag,
            flags=re.IGNORECASE,
        )

        style_match = re.search(
            r'\bstyle=["\']([^"\']+)["\']',
            tag,
            flags=re.IGNORECASE,
        )

        if src_match:
            print(
                "src:",
                absolute_url(
                    src_match.group(1)
                ),
            )

        if data_src_match:
            print(
                "data-src:",
                absolute_url(
                    data_src_match.group(1)
                ),
            )

        if style_match:
            print(
                "style:",
                style_match.group(1),
            )


# ============================================================
# CSS background-image を探す
# ============================================================

def inspect_background_images(html):
    pattern = re.compile(
        r'background(?:-image)?\s*:\s*'
        r'url\(\s*["\']?'
        r'([^)"\']+)'
        r'["\']?\s*\)',
        flags=re.IGNORECASE,
    )

    urls = []

    for match in pattern.finditer(
        html
    ):
        url = absolute_url(
            match.group(1)
        )

        if url not in urls:
            urls.append(url)

    print()
    print(
        "========================================"
    )
    print(
        "background-image候補"
    )
    print(
        "========================================"
    )

    print(
        f"{len(urls)}件"
    )

    for url in urls:
        print(url)


# ============================================================
# OG画像等を探す
# ============================================================

def inspect_meta_images(html):
    patterns = [
        (
            "og:image",
            re.compile(
                r'<meta\b'
                r'(?=[^>]*property=["\']og:image["\'])'
                r'[^>]*content=["\']([^"\']+)["\']'
                r'[^>]*>',
                flags=re.IGNORECASE,
            ),
        ),
        (
            "twitter:image",
            re.compile(
                r'<meta\b'
                r'(?=[^>]*name=["\']twitter:image["\'])'
                r'[^>]*content=["\']([^"\']+)["\']'
                r'[^>]*>',
                flags=re.IGNORECASE,
            ),
        ),
    ]

    print()
    print(
        "========================================"
    )
    print(
        "META画像候補"
    )
    print(
        "========================================"
    )

    found = False

    for label, pattern in patterns:

        matches = pattern.findall(
            html
        )

        for match in matches:
            found = True

            print(
                f"{label}: "
                f"{absolute_url(match)}"
            )

    if not found:
        print(
            "画像系metaタグは"
            "見つかりませんでした。"
        )


# ============================================================
# 記事リンク取得
# ============================================================

def extract_article_links(html):
    pattern = re.compile(
        r'href=["\']'
        r'([^"\']*/blog/detail/(\d+)/?[^"\']*)'
        r'["\']',
        flags=re.IGNORECASE,
    )

    articles = []
    seen_ids = set()

    for match in pattern.finditer(
        html
    ):

        raw_url = match.group(1)
        article_id = match.group(2)

        if article_id in seen_ids:
            continue

        seen_ids.add(
            article_id
        )

        articles.append(
            {
                "id": article_id,
                "url": absolute_url(
                    raw_url
                ),
            }
        )

    return articles


# ============================================================
# HTML内の画像らしいURLを広く探す
# ============================================================

def inspect_image_like_urls(html):
    pattern = re.compile(
        r'''(?:
            https?://[^\s"'<>]+
            |
            /[^\s"'<>]+
        )
        \.(?:
            jpg|
            jpeg|
            png|
            webp|
            gif
        )
        (?:\?[^\s"'<>]*)?
        ''',
        flags=(
            re.IGNORECASE |
            re.VERBOSE
        ),
    )

    urls = []

    for match in pattern.finditer(
        html
    ):

        url = absolute_url(
            match.group(0)
        )

        if url not in urls:
            urls.append(url)

    print()
    print(
        "========================================"
    )
    print(
        "HTML内の画像URL候補"
    )
    print(
        "========================================"
    )

    print(
        f"{len(urls)}件"
    )

    for url in urls:
        print(url)


# ============================================================
# ページ診断
# ============================================================

def diagnose_page(
    label,
    url,
):
    print()
    print()
    print(
        "########################################"
    )
    print(label)
    print(
        "########################################"
    )

    print(
        "URL:",
        url,
    )

    html = fetch_html(
        url
    )

    print(
        "HTML文字数:",
        len(html),
    )

    print()
    print(
        "========================================"
    )
    print(
        "IMGタグ"
    )
    print(
        "========================================"
    )

    inspect_images(
        html
    )

    inspect_background_images(
        html
    )

    inspect_meta_images(
        html
    )

    inspect_image_like_urls(
        html
    )

    return html


# ============================================================
# メイン
# ============================================================

def main():

    print(
        "Member Diary "
        "サムネイル診断を開始します。"
    )


    # ========================================================
    # まず一覧ページを確認
    # ========================================================

    list_url = (
        f"{LIST_URL}?page=1&writer=0"
    )

    list_html = diagnose_page(
        "Member Diary 一覧ページ",
        list_url,
    )


    # ========================================================
    # 一覧から最新記事を取得
    # ========================================================

    articles = extract_article_links(
        list_html
    )


    print()
    print()
    print(
        "========================================"
    )
    print(
        "検出した記事"
    )
    print(
        "========================================"
    )

    print(
        f"{len(articles)}件"
    )


    for article in articles[
        :10
    ]:
        print(
            article["id"],
            article["url"],
        )


    if not articles:
        raise RuntimeError(
            "Member Diaryの記事リンクを"
            "取得できませんでした。"
        )


    # ========================================================
    # 最新記事の個別ページを確認
    # ========================================================

    latest_article = (
        articles[0]
    )


    diagnose_page(
        (
            "Member Diary "
            f"個別ページ "
            f"(記事ID {latest_article['id']})"
        ),
        latest_article["url"],
    )


    print()
    print()
    print(
        "========================================"
    )
    print(
        "診断完了"
    )
    print(
        "========================================"
    )

    print(
        "一覧ページと最新記事ページの"
        "画像関連HTMLを出力しました。"
    )


if __name__ == "__main__":
    main()
