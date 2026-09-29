import re
import urllib.request
from html import unescape


# ============================================================
# 設定
# ============================================================

BASE_URL = "https://ini-official.com"

RADIO_URL = (
    f"{BASE_URL}/streams/list/6/0/"
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
            response.headers
            .get_content_charset()
            or "utf-8"
        )

        body = response.read()

        print(
            "HTTP status:",
            response.status,
        )

        print(
            "Content-Type:",
            response.headers.get(
                "Content-Type"
            ),
        )

        print(
            "HTML bytes:",
            len(body),
        )

        return body.decode(
            charset,
            errors="replace",
        )


# ============================================================
# HTMLタグを除いて見やすくする
# ============================================================

def strip_tags(value):

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
# streams/detail のリンクを探す
# ============================================================

def find_detail_links(page_html):

    pattern = re.compile(
        r'<a\b[^>]*'
        r'href=["\']'
        r'([^"\']*'
        r'/streams/detail/'
        r'(\d+)'
        r'[^"\']*)'
        r'["\'][^>]*>',
        flags=re.IGNORECASE,
    )

    results = []

    seen_ids = set()

    for match in pattern.finditer(
        page_html
    ):

        url = match.group(1)

        stream_id = match.group(2)

        if stream_id in seen_ids:
            continue

        seen_ids.add(
            stream_id
        )

        results.append(
            {
                "id": stream_id,
                "url": url,
                "position": match.start(),
            }
        )

    return results


# ============================================================
# 各リンク周辺の生HTMLを表示
#
# クラス名・タイトル・日付・画像属性を
# 推測せず実際に確認するため。
# ============================================================

def print_link_context(
    page_html,
    detail,
):

    position = detail[
        "position"
    ]

    start = max(
        0,
        position - 500,
    )

    end = min(
        len(page_html),
        position + 2500,
    )

    context = page_html[
        start:end
    ]


    print()
    print(
        "=" * 80
    )

    print(
        "STREAM ID:",
        detail["id"],
    )

    print(
        "URL:",
        detail["url"],
    )

    print(
        "-" * 80
    )

    print(
        "RAW HTML AROUND LINK"
    )

    print(
        "-" * 80
    )

    print(
        context
    )

    print(
        "-" * 80
    )

    print(
        "TEXT VERSION"
    )

    print(
        "-" * 80
    )

    print(
        strip_tags(
            context
        )
    )


# ============================================================
# imgタグを調査
# ============================================================

def inspect_images(
    page_html
):

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


    interesting_images = []

    for tag in image_tags:

        lower = tag.lower()

        if (
            "stream" in lower
            or
            "radio" in lower
            or
            "detail" in lower
            or
            "background-image" in lower
            or
            "data-src" in lower
        ):
            interesting_images.append(
                tag
            )


    print(
        "interesting img tags:",
        len(
            interesting_images
        ),
    )


    for index, tag in enumerate(
        interesting_images[:30],
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
# background-imageを調査
# ============================================================

def inspect_background_images(
    page_html
):

    matches = re.findall(
        r'background-image\s*:\s*'
        r'url\([^)]*\)',
        page_html,
        flags=re.IGNORECASE,
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
        "background-image:",
        len(matches),
    )


    for index, value in enumerate(
        matches[:30],
        start=1,
    ):

        print(
            f"[{index}]",
            value,
        )


# ============================================================
# class名を一覧化
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

        for class_name in value.split():

            classes.add(
                class_name
            )


    interesting = sorted(
        class_name
        for class_name in classes
        if (
            "stream" in class_name.lower()
            or
            "radio" in class_name.lower()
            or
            "title" in class_name.lower()
            or
            "date" in class_name.lower()
            or
            "thumb" in class_name.lower()
            or
            "list" in class_name.lower()
            or
            "item" in class_name.lower()
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
# 最新RadioがHTMLに存在するか確認
# ============================================================

def inspect_latest_radio(
    page_html
):

    print()
    print(
        "=" * 80
    )

    print(
        "LATEST RADIO CHECK"
    )

    print(
        "=" * 80
    )


    checks = [
        "きょうすけ らじお。",
        "きょうすけらじお",
        "#12",
        "2026.09.29",
        "2026-09-29",
        "2026/09/29",
    ]


    for keyword in checks:

        found = (
            keyword in page_html
        )

        print(
            f"{keyword!r}:",
            "FOUND"
            if found
            else "NOT FOUND",
        )


        if found:

            position = (
                page_html.find(
                    keyword
                )
            )

            start = max(
                0,
                position - 700,
            )

            end = min(
                len(page_html),
                position + 1500,
            )


            print(
                page_html[
                    start:end
                ]
            )

            print(
                "-" * 80
            )


# ============================================================
# ページネーション調査
# ============================================================

def inspect_pagination(
    page_html
):

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


    print(
        "pagination links:",
        len(unique_links),
    )


    for link in unique_links:

        print(
            " ",
            link,
        )


# ============================================================
# メイン
# ============================================================

def main():

    print(
        "INI Radio HTML診断を開始します。"
    )

    print(
        "URL:",
        RADIO_URL,
    )

    print()


    page_html = fetch_html(
        RADIO_URL
    )


    # ========================================================
    # 最新Radio存在確認
    # ========================================================

    inspect_latest_radio(
        page_html
    )


    # ========================================================
    # streams/detailリンク
    # ========================================================

    details = find_detail_links(
        page_html
    )


    print()
    print(
        "=" * 80
    )

    print(
        "STREAM DETAIL LINKS"
    )

    print(
        "=" * 80
    )

    print(
        "unique stream IDs:",
        len(details),
    )


    for detail in details:

        print(
            " ",
            detail["id"],
            detail["url"],
        )


    # ========================================================
    # 最新側のリンク周辺HTML
    #
    # ログが巨大になりすぎないよう
    # 最初の5件だけ表示
    # ========================================================

    print()
    print(
        "=" * 80
    )

    print(
        "LATEST 5 STREAM HTML BLOCKS"
    )

    print(
        "=" * 80
    )


    for detail in details[:5]:

        print_link_context(
            page_html,
            detail,
        )


    # ========================================================
    # class
    # ========================================================

    inspect_classes(
        page_html
    )


    # ========================================================
    # img
    # ========================================================

    inspect_images(
        page_html
    )


    # ========================================================
    # background-image
    # ========================================================

    inspect_background_images(
        page_html
    )


    # ========================================================
    # pagination
    # ========================================================

    inspect_pagination(
        page_html
    )


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

    print(
        "このスクリプトは"
        "GitHub上のファイルを変更しません。"
    )

    print(
        "JSONファイルも作成・更新しません。"
    )


if __name__ == "__main__":

    main()
