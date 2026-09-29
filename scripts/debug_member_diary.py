import re
import urllib.parse
import urllib.request


BASE_URL = "https://ini-official.com/blog/list/1/0/"

USER_AGENT = (
    "Mozilla/5.0 "
    "(Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/140.0.0.0 Safari/537.36"
)


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


def main():
    query = urllib.parse.urlencode(
        {
            "page": 65,
            "writer": 0,
        }
    )

    url = f"{BASE_URL}?{query}"

    print("65ページ目を取得します。")
    print(url)
    print()

    page_html = fetch_html(url)

    # /blog/detail/○○/ をすべて探す
    pattern = re.compile(
        r'<a\b[^>]*'
        r'href=["\']'
        r'([^"\']*/blog/detail/(\d+)/?[^"\']*)'
        r'["\'][^>]*>'
        r'(.*?)'
        r'</a>',
        re.IGNORECASE | re.DOTALL,
    )

    matches = list(
        pattern.finditer(page_html)
    )

    print(
        f"記事リンク候補：{len(matches)}件"
    )
    print()

    for index, match in enumerate(
        matches,
        start=1,
    ):
        article_id = match.group(2)

        # リンクの前後1500文字を表示
        start = max(
            0,
            match.start() - 1500,
        )

        end = min(
            len(page_html),
            match.end() + 1500,
        )

        context = page_html[start:end]

        print(
            "=" * 80
        )
        print(
            f"候補 {index} / 記事ID {article_id}"
        )
        print(
            "=" * 80
        )

        print(context)

        print()
        print()


if __name__ == "__main__":
    main()
