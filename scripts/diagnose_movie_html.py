import re
import urllib.request


# ============================================================
# 設定
# ============================================================

TARGET_URL = "https://ini-official.com/movies/list/15/0/"
TARGET_MOVIE_ID = "589"

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
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
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
# Movie 589 周辺を表示
# ============================================================

def print_movie_context(page_html):
    patterns = [
        f"/movies/detail/{TARGET_MOVIE_ID}",
        f"/movies/detail/{TARGET_MOVIE_ID}/",
    ]

    position = -1

    for pattern in patterns:
        position = page_html.find(pattern)

        if position != -1:
            break

    if position == -1:
        print()
        print("=" * 80)
        print(
            f"Movie {TARGET_MOVIE_ID} のURLが"
            "HTML内に見つかりませんでした。"
        )
        print("=" * 80)
        return

    print()
    print("=" * 80)
    print(
        f"Movie {TARGET_MOVIE_ID} を発見しました。"
    )
    print("=" * 80)

    print(
        f"HTML内の位置: {position}"
    )

    # 前後3000文字を表示
    start = max(
        0,
        position - 3000,
    )

    end = min(
        len(page_html),
        position + 3000,
    )

    context = page_html[
        start:end
    ]

    print()
    print("----- Movie周辺HTML START -----")
    print()
    print(context)
    print()
    print("----- Movie周辺HTML END -----")


# ============================================================
# Movieリンク周辺のタグ情報
# ============================================================

def inspect_movie_link(page_html):
    pattern = re.compile(
        rf'<a\b[^>]*'
        rf'href=["\'][^"\']*'
        rf'/movies/detail/{TARGET_MOVIE_ID}'
        rf'/?[^"\']*["\']'
        rf'[^>]*>'
        rf'.*?'
        rf'</a>',
        flags=re.IGNORECASE | re.DOTALL,
    )

    match = pattern.search(
        page_html
    )

    print()
    print("=" * 80)
    print("Movieリンク要素")
    print("=" * 80)

    if not match:
        print(
            "<a>要素全体を"
            "抽出できませんでした。"
        )
        return

    print(
        match.group(0)
    )


# ============================================================
# Movie周辺に登場するclass名を表示
# ============================================================

def inspect_classes(page_html):
    target = (
        f"/movies/detail/"
        f"{TARGET_MOVIE_ID}"
    )

    position = page_html.find(
        target
    )

    if position == -1:
        return

    start = max(
        0,
        position - 3000,
    )

    end = min(
        len(page_html),
        position + 3000,
    )

    context = page_html[
        start:end
    ]

    classes = re.findall(
        r'class=["\']([^"\']+)["\']',
        context,
        flags=re.IGNORECASE,
    )

    print()
    print("=" * 80)
    print(
        "Movie周辺に存在するclass"
    )
    print("=" * 80)

    if not classes:
        print(
            "class属性は"
            "見つかりませんでした。"
        )
        return

    seen = set()

    for class_value in classes:
        if class_value in seen:
            continue

        seen.add(
            class_value
        )

        print(
            class_value
        )


# ============================================================
# 日付周辺を確認
# ============================================================

def inspect_dates(page_html):
    target = (
        f"/movies/detail/"
        f"{TARGET_MOVIE_ID}"
    )

    position = page_html.find(
        target
    )

    if position == -1:
        return

    start = max(
        0,
        position - 3000,
    )

    end = min(
        len(page_html),
        position + 3000,
    )

    context = page_html[
        start:end
    ]

    dates = re.findall(
        r'\d{4}'
        r'[./-]'
        r'\d{1,2}'
        r'[./-]'
        r'\d{1,2}'
        r'\.?',
        context,
    )

    print()
    print("=" * 80)
    print(
        "Movie周辺で検出した日付"
    )
    print("=" * 80)

    if not dates:
        print(
            "日付らしい文字列は"
            "見つかりませんでした。"
        )
        return

    for date in dates:
        print(date)


# ============================================================
# ページ内のMovieリンク一覧
# ============================================================

def inspect_movie_ids(page_html):
    ids = re.findall(
        r'/movies/detail/(\d+)',
        page_html,
        flags=re.IGNORECASE,
    )

    # 重複排除しつつ順序維持
    unique_ids = list(
        dict.fromkeys(ids)
    )

    print()
    print("=" * 80)
    print(
        "このページで検出したMovie ID"
    )
    print("=" * 80)

    print(
        f"検出件数: {len(unique_ids)}"
    )

    print(
        unique_ids
    )


# ============================================================
# ページ送り周辺を確認
# ============================================================

def inspect_pagination(page_html):
    print()
    print("=" * 80)
    print(
        "page= を含むリンク"
    )
    print("=" * 80)

    links = re.findall(
        r'href=["\']([^"\']*'
        r'(?:\?|&)page=\d+'
        r'[^"\']*)["\']',
        page_html,
        flags=re.IGNORECASE,
    )

    unique_links = list(
        dict.fromkeys(links)
    )

    if not unique_links:
        print(
            "page= を含むリンクは"
            "見つかりませんでした。"
        )
        return

    for link in unique_links:
        print(link)


# ============================================================
# メイン
# ============================================================

def main():
    print(
        "INI Movie HTML診断を開始します。"
    )

    print(
        f"取得URL: {TARGET_URL}"
    )

    print()

    page_html = fetch_html(
        TARGET_URL
    )

    print(
        "HTML取得成功"
    )

    print(
        f"HTML文字数: "
        f"{len(page_html):,}"
    )

    inspect_movie_ids(
        page_html
    )

    print_movie_context(
        page_html
    )

    inspect_movie_link(
        page_html
    )

    inspect_classes(
        page_html
    )

    inspect_dates(
        page_html
    )

    inspect_pagination(
        page_html
    )

    print()
    print("=" * 80)
    print(
        "診断完了"
    )
    print("=" * 80)

    print(
        "ファイル作成・JSON更新などは"
        "行っていません。"
    )


if __name__ == "__main__":
    main()
