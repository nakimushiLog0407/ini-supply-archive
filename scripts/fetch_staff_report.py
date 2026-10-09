import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime


# ============================================================
# 設定
# ============================================================

BASE_URL = "https://ini-official.com"
LIST_URL = f"{BASE_URL}/blog/list/3/0/"

OUTPUT_FILE = "data/staff_report.json"
TEMP_FILE = OUTPUT_FILE + ".tmp"

REQUEST_INTERVAL = 0.5

MAX_PAGES = 500

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
# HTML → プレーンテキスト
# ============================================================

def clean_text(value):
    if value is None:
        return None

    value = re.sub(
        r"<[^>]+>",
        "",
        value,
        flags=re.DOTALL,
    )

    # &amp; や &#x1F62C; などを通常文字へ
    value = html.unescape(value)

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


# ============================================================
# class属性に指定classが含まれるか調べる
# ============================================================

def extract_p_by_class(block_html, class_name):
    pattern = re.compile(
        r'<p\b'
        r'(?=[^>]*\bclass=["\'][^"\']*\b'
        + re.escape(class_name)
        + r'\b[^"\']*["\'])'
        r'[^>]*>'
        r'(.*?)'
        r'</p>',
        flags=re.IGNORECASE | re.DOTALL,
    )

    match = pattern.search(
        block_html
    )

    if not match:
        return None

    return clean_text(
        match.group(1)
    )


# ============================================================
# メンバー名取得
#
# class="category user"
# class="user category"
# の両方に対応
# ============================================================

def extract_member(block_html):
    p_pattern = re.compile(
        r'<p\b([^>]*)>'
        r'(.*?)'
        r'</p>',
        flags=re.IGNORECASE | re.DOTALL,
    )

    for match in p_pattern.finditer(
        block_html
    ):
        attributes = match.group(1)

        class_match = re.search(
            r'class=["\']([^"\']*)["\']',
            attributes,
            flags=re.IGNORECASE,
        )

        if not class_match:
            continue

        classes = set(
            class_match.group(1).split()
        )

        if (
            "category" in classes
            and "user" in classes
        ):
            return clean_text(
                match.group(2)
            )

    return None


# ============================================================
# 記事リンク <a> を抽出
#
# /blog/detail/数字/
# をhrefに持つaタグだけを対象にする
# ============================================================

def extract_article_links(page_html):
    pattern = re.compile(
        r'<a\b'
        r'(?P<attributes>[^>]*?)'
        r'href=["\']'
        r'(?P<url>[^"\']*'
        r'/blog/detail/'
        r'(?P<id>\d+)'
        r'/?[^"\']*)'
        r'["\']'
        r'(?P<attributes_after>[^>]*)>'
        r'(?P<body>.*?)'
        r'</a>',
        flags=re.IGNORECASE | re.DOTALL,
    )

    results = []

    for match in pattern.finditer(
        page_html
    ):
        results.append(
            {
                "article_id":
                    match.group("id"),
                "raw_url":
                    match.group("url"),
                "body":
                    match.group("body"),
            }
        )

    return results


# ============================================================
# 日付を正規化
# ============================================================

def normalize_date(
    raw_date,
    article_id,
):
    # 念のため前後の空白を除去
    raw_date = raw_date.strip()

    formats = [
        "%Y.%m.%d",
        "%Y.%m.%d.",
        "%Y-%m-%d",
        "%Y/%m/%d",
    ]

    for date_format in formats:
        try:
            parsed = datetime.strptime(
                raw_date,
                date_format,
            )

            return parsed.strftime(
                "%Y-%m-%d"
            )

        except ValueError:
            continue

    raise ValueError(
        f"記事 {article_id}: "
        f"日付形式を解析できません: "
        f"{raw_date}"
    )


# ============================================================
# 1記事を解析
# ============================================================

def parse_article(article_link):
    article_id = article_link[
        "article_id"
    ]

    body = article_link[
        "body"
    ]

    # --------------------------------------------------------
    # タイトル
    # --------------------------------------------------------

    title = extract_p_by_class(
        body,
        "tit",
    )

    # --------------------------------------------------------
    # 公開日
    # --------------------------------------------------------

    raw_date = extract_p_by_class(
        body,
        "date",
    )

    # --------------------------------------------------------
    # メンバー
    # --------------------------------------------------------

    member = extract_member(
        body
    )

    # --------------------------------------------------------
    # 必須項目チェック
    # --------------------------------------------------------

    missing = []

    if not title:
        missing.append(
            "title"
        )

    if not raw_date:
        missing.append(
            "date"
        )


    if missing:
        raise ValueError(
            f"記事 {article_id}: "
            f"{', '.join(missing)} "
            "を取得できませんでした"
        )

    normalized_date = normalize_date(
        raw_date,
        article_id,
    )

    # URLは記事IDから正規形を作る
    article_url = (
        f"{BASE_URL}/blog/detail/"
        f"{article_id}/"
    )

    return {
        "id": (
            f"staff-report-"
            f"{article_id}"
        ),
        "type": "staff_report",
        "group": "fc",
        "date": normalized_date,
        "title": title,
        "url": article_url,
    }


# ============================================================
# 1ページ解析
# ============================================================

def parse_page(
    page_html,
    page_number,
):
    article_links = (
        extract_article_links(
            page_html
        )
    )

    # --------------------------------------------------------
    # デバッグ情報
    # --------------------------------------------------------

    title_count = len(
        re.findall(
            r'<p\b'
            r'(?=[^>]*\bclass=["\'][^"\']*\btit\b)',
            page_html,
            flags=re.IGNORECASE,
        )
    )

    date_count = len(
        re.findall(
            r'<p\b'
            r'(?=[^>]*\bclass=["\'][^"\']*\bdate\b)',
            page_html,
            flags=re.IGNORECASE,
        )
    )

    member_count = 0

    p_pattern = re.compile(
        r'<p\b([^>]*)>',
        flags=re.IGNORECASE,
    )

    for match in p_pattern.finditer(
        page_html
    ):
        class_match = re.search(
            r'class=["\']([^"\']*)["\']',
            match.group(1),
            flags=re.IGNORECASE,
        )

        if not class_match:
            continue

        classes = set(
            class_match.group(1).split()
        )

        if (
            "category" in classes
            and "user" in classes
        ):
            member_count += 1

    print(
        "  検出："
        f"記事リンク {len(article_links)} / "
        f"タイトル {title_count} / "
        f"日付 {date_count} / "
        f"メンバー {member_count}"
    )

    # --------------------------------------------------------
    # 記事リンクが0件
    #
    # これは最終ページを越えた可能性があるので
    # fetch_all_diaries側で判定する
    # --------------------------------------------------------

    if not article_links:
        return [], []

    # --------------------------------------------------------
    # 同じ記事へのリンクが複数ある場合に備える
    # --------------------------------------------------------

    grouped = {}

    for article_link in article_links:
        article_id = article_link[
            "article_id"
        ]

        grouped.setdefault(
            article_id,
            [],
        ).append(
            article_link
        )

    articles = []
    failures = []

    for (
        article_id,
        candidates,
    ) in grouped.items():

        parsed = None
        last_error = None

        # 同じ記事へのリンクが複数あれば、
        # 正しい情報を持つリンクを順番に試す
        for candidate in candidates:
            try:
                parsed = parse_article(
                    candidate
                )

                break

            except ValueError as error:
                last_error = error

        if parsed:
            articles.append(
                parsed
            )

        else:
            if last_error:
                message = str(
                    last_error
                )
            else:
                message = (
                    f"記事 {article_id}: "
                    "解析できませんでした"
                )

            failures.append(
                {
                    "page":
                        page_number,
                    "article_id":
                        article_id,
                    "message":
                        message,
                }
            )

    return articles, failures


# ============================================================
# 1ページ取得
# ============================================================

def fetch_page(page_number):
    query = urllib.parse.urlencode(
        {
            "page": page_number,
            "writer": 0,
        }
    )

    url = (
        f"{LIST_URL}?{query}"
    )

    print(
        f"Staff Report "
        f"{page_number}ページ目を確認..."
    )

    page_html = fetch_html(
        url
    )

    articles, failures = parse_page(
        page_html,
        page_number,
    )

    print(
        f"  {len(articles)}件取得"
    )

    if failures:
        for failure in failures:
            print(
                "  警告："
                f"{failure['message']}"
            )

    return (
        articles,
        failures,
    )


# ============================================================
# 全ページ取得
# ============================================================

def fetch_all_diaries():
    all_articles = []

    all_failures = []

    seen_ids = set()

    previous_page_ids = None

    for page_number in range(
        1,
        MAX_PAGES + 1,
    ):
        (
            articles,
            failures,
        ) = fetch_page(
            page_number
        )

        all_failures.extend(
            failures
        )

        # ----------------------------------------------------
        # 記事も解析失敗も0件
        # → 最終ページを越えたと判断
        # ----------------------------------------------------

        if (
            not articles
            and not failures
        ):
            print(
                "記事のないページに"
                "到達しました。"
            )

            break

        current_page_ids = {
            article["id"]
            for article in articles
        }

        # ----------------------------------------------------
        # 同じページが繰り返された場合の安全装置
        # ----------------------------------------------------

        if (
            previous_page_ids is not None
            and current_page_ids
            == previous_page_ids
            and not failures
        ):
            raise RuntimeError(
                f"{page_number}ページ目が"
                "直前のページと完全に同じです。"
                "ページネーションを"
                "正常に取得できていない"
                "可能性があります。"
            )

        previous_page_ids = (
            current_page_ids
        )

        # ----------------------------------------------------
        # 全体へ追加
        # ----------------------------------------------------

        for article in articles:
            article_id = article[
                "id"
            ]

            if article_id in seen_ids:
                continue

            seen_ids.add(
                article_id
            )

            all_articles.append(
                article
            )

        time.sleep(
            REQUEST_INTERVAL
        )

    else:
        raise RuntimeError(
            f"{MAX_PAGES}ページまで"
            "到達しました。"
            "最終ページを検出できませんでした。"
        )

    # --------------------------------------------------------
    # 解析失敗が1件でもあれば保存禁止
    # --------------------------------------------------------

    if all_failures:
        print()
        print(
            "=" * 60
        )

        print(
            "解析失敗した記事"
        )

        print(
            "=" * 60
        )

        for failure in all_failures:
            print(
                f"ページ "
                f"{failure['page']} / "
                f"記事 "
                f"{failure['article_id']} / "
                f"{failure['message']}"
            )

        print(
            "=" * 60
        )

        raise RuntimeError(
            f"{len(all_failures)}件の"
            "Staff Reportを"
            "解析できませんでした。"
            "staff_report.jsonは"
            "更新しません。"
        )

    # --------------------------------------------------------
    # 0件も保存禁止
    # --------------------------------------------------------

    if not all_articles:
        raise RuntimeError(
            "Staff Reportを"
            "1件も取得できませんでした。"
            "staff_report.jsonは"
            "更新しません。"
        )

    # --------------------------------------------------------
    # 日付 → 記事ID順
    # --------------------------------------------------------

    def sort_key(article):
        article_number = int(
            article[
                "id"
            ].split("-")[-1]
        )

        return (
            article["date"],
            article_number,
        )

    all_articles.sort(
        key=sort_key
    )

    return all_articles


# ============================================================
# JSON保存
# ============================================================

def save_diaries(diaries):
    output_dir = os.path.dirname(
        OUTPUT_FILE
    )

    if output_dir:
        os.makedirs(
            output_dir,
            exist_ok=True,
        )

    # --------------------------------------------------------
    # まず一時ファイルに完全なJSONを書く
    # --------------------------------------------------------

    with open(
        TEMP_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            diaries,
            file,
            ensure_ascii=False,
            indent=2,
        )

        file.write(
            "\n"
        )

        file.flush()

        os.fsync(
            file.fileno()
        )

    # --------------------------------------------------------
    # 一時JSONを読み直して検証
    # --------------------------------------------------------

    with open(
        TEMP_FILE,
        "r",
        encoding="utf-8",
    ) as file:
        verification = json.load(
            file
        )

    if len(verification) != len(
        diaries
    ):
        raise RuntimeError(
            "保存前検証で件数が"
            "一致しませんでした。"
        )

    # --------------------------------------------------------
    # 全部正常なら本番ファイルを置換
    # --------------------------------------------------------

    os.replace(
        TEMP_FILE,
        OUTPUT_FILE,
    )


# ============================================================
# メイン
# ============================================================

def main():
    print(
        "INI Staff Report の"
        "全件取得を開始します。"
    )

    print()

    try:
        diaries = (
            fetch_all_diaries()
        )

        print()
        print(
            f"全 {len(diaries)}件を"
            "正常に取得しました。"
        )

        print(
            "全記事の解析成功を"
            "確認しました。"
        )

        save_diaries(
            diaries
        )

        print()
        print(
            f"{OUTPUT_FILE} を"
            "更新しました。"
        )

    except Exception:
        # ----------------------------------------------------
        # エラー時に一時ファイルだけ削除
        # 既存staff_report.jsonには触らない
        # ----------------------------------------------------

        if os.path.exists(
            TEMP_FILE
        ):
            try:
                os.remove(
                    TEMP_FILE
                )

            except OSError:
                pass

        print()
        print(
            "取得に失敗しました。"
        )

        print(
            "staff_report.jsonは"
            "更新していません。"
        )

        raise


if __name__ == "__main__":
    main()
