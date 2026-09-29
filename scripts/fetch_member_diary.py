import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path


# ========================================
# 基本設定
# ========================================

BASE_URL = "https://ini-official.com"

LIST_URL = (
    "https://ini-official.com/"
    "blog/list/1/0/"
)

OUTPUT_FILE = Path("data/supplies.json")

USER_AGENT = (
    "Mozilla/5.0 "
    "(Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/140.0.0.0 Safari/537.36"
)

# 万一サイト側の仕様変更などで
# 「記事なし」を検出できなかった場合の
# 無限ループ防止用
MAX_PAGES = 200


# ========================================
# HTMLを取得
# ========================================

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
            "Accept-Language": (
                "ja,en-US;q=0.9,en;q=0.8"
            ),
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

        return (
            response
            .read()
            .decode(
                charset,
                errors="replace",
            )
        )


# ========================================
# HTMLからプレーンテキストを作る
# ========================================

def clean_text(value):
    # 改行系タグを空白に変換
    value = re.sub(
        r"<br\s*/?>",
        " ",
        value,
        flags=re.IGNORECASE,
    )

    # その他のHTMLタグを削除
    value = re.sub(
        r"<[^>]+>",
        " ",
        value,
    )

    # &amp; などを元の文字へ戻す
    value = html.unescape(value)

    # 連続する空白・改行を1つにする
    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


# ========================================
# 既存データを読み込む
# ========================================

def load_existing_supplies():
    if not OUTPUT_FILE.exists():
        return []

    with OUTPUT_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise RuntimeError(
            "data/supplies.json の形式が"
            "配列ではありません。"
        )

    return data


# ========================================
# 記事URLを絶対URLへ変換
# ========================================

def make_absolute_url(url):
    return urllib.parse.urljoin(
        BASE_URL,
        html.unescape(url),
    )


# ========================================
# Member Diaryの記事リンクを抽出
# ========================================

def find_article_links(page_html):
    pattern = re.compile(
        r'<a\b[^>]*'
        r'href=["\']'
        r'([^"\']*'
        r'/blog/detail/(\d+)/?'
        r'[^"\']*)'
        r'["\'][^>]*>',
        re.IGNORECASE,
    )

    links = []

    seen_ids = set()

    for match in pattern.finditer(
        page_html
    ):
        relative_url = match.group(1)
        article_id = match.group(2)

        if article_id in seen_ids:
            continue

        seen_ids.add(article_id)

        links.append(
            {
                "article_id": article_id,
                "url": make_absolute_url(
                    relative_url
                ),
                "start": match.start(),
            }
        )

    return links


# ========================================
# 1記事分のHTML範囲を切り出す
# ========================================

def extract_article_blocks(page_html):
    links = find_article_links(
        page_html
    )

    blocks = []

    if not links:
        return blocks

    for index, link in enumerate(links):
        start = link["start"]

        if index + 1 < len(links):
            end = links[index + 1][
                "start"
            ]
        else:
            # 最後の記事は後ろをある程度
            # 広めに取得する
            end = min(
                len(page_html),
                start + 12000,
            )

        block = page_html[
            start:end
        ]

        blocks.append(
            {
                "article_id":
                    link["article_id"],
                "url":
                    link["url"],
                "html":
                    block,
            }
        )

    return blocks


# ========================================
# 日付を抽出
# ========================================

def extract_date(text):
    match = re.search(
        r"(20\d{2})"
        r"[./-]"
        r"(\d{1,2})"
        r"[./-]"
        r"(\d{1,2})",
        text,
    )

    if not match:
        return None, None

    year = int(
        match.group(1)
    )

    month = int(
        match.group(2)
    )

    day = int(
        match.group(3)
    )

    normalized = (
        f"{year:04d}-"
        f"{month:02d}-"
        f"{day:02d}"
    )

    return normalized, match


# ========================================
# 1記事から必要情報を抽出
# ========================================

def parse_article_block(article):
    article_id = article[
        "article_id"
    ]

    url = article["url"]

    block_html = article["html"]

    text = clean_text(
        block_html
    )

    if not text:
        return None

    date, date_match = (
        extract_date(text)
    )

    if not date or not date_match:
        print(
            "  警告："
            f"記事 {article_id} の"
            "公開日を取得できませんでした。"
        )

        return None

    before_date = (
        text[
            :date_match.start()
        ]
        .strip()
    )

    after_date = (
        text[
            date_match.end():
        ]
        .strip()
    )


    # ====================================
    # タイトル
    # ====================================

    # リンクの中に画像などがあっても、
    # 日付より前のテキストの最後側に
    # タイトルがあることを想定する。
    #
    # 不要な空白はclean_textで
    # すでに整理済み。

    title = before_date


    # ====================================
    # メンバー名
    # ====================================

    # 日付直後に表示されるテキストを
    # メンバー名候補として取得。
    #
    # 次の記事やページナビゲーションまで
    # blockを切っているので、
    # 最初の短いテキストを採用する。

    member = after_date

    # メンバー名の後ろに余計な文字列が
    # 入った場合に備え、
    # HTML構造上の区切り候補を使って
    # 短くする。
    member = re.split(
        r"\s{2,}",
        member,
        maxsplit=1,
    )[0].strip()


    # ====================================
    # 最低限の妥当性チェック
    # ====================================

    if not title:
        print(
            "  警告："
            f"記事 {article_id} の"
            "タイトルを取得できませんでした。"
        )

        return None

    if not member:
        print(
            "  警告："
            f"記事 {article_id} の"
            "メンバー名を取得できませんでした。"
        )

        return None


    return {
        "id": (
            f"member-diary-"
            f"{article_id}"
        ),
        "type": "member_diary",
        "group": "fc",
        "date": date,
        "title": title,
        "member": member,
        "url": url,
    }


# ========================================
# 一覧ページから記事を抽出
# ========================================

def parse_diary_entries(page_html):
    articles = (
        extract_article_blocks(
            page_html
        )
    )

    entries = []

    seen_ids = set()

    for article in articles:
        entry = parse_article_block(
            article
        )

        if not entry:
            continue

        if entry["id"] in seen_ids:
            continue

        seen_ids.add(
            entry["id"]
        )

        entries.append(
            entry
        )

    return entries


# ========================================
# 指定した一覧ページを取得
# ========================================

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
        "Member Diary "
        f"{page_number}ページ目を確認..."
    )

    page_html = fetch_html(
        url
    )

    entries = parse_diary_entries(
        page_html
    )

    print(
        f"  {len(entries)}件取得"
    )

    return entries


# ========================================
# 初回：過去記事をすべて取得
# ========================================

def fetch_all_diaries():
    diaries = []

    seen_ids = set()

    for page_number in range(
        1,
        MAX_PAGES + 1,
    ):
        page_entries = fetch_page(
            page_number
        )

        # 記事が1件もなければ終了
        if not page_entries:
            print(
                "記事のないページに"
                "到達しました。"
            )

            break

        new_count = 0

        for entry in page_entries:
            if entry["id"] in seen_ids:
                continue

            seen_ids.add(
                entry["id"]
            )

            diaries.append(
                entry
            )

            new_count += 1

        # 同じページが繰り返される
        # サイト仕様だった場合の
        # 無限ループ防止
        if new_count == 0:
            print(
                "新しい記事がないページに"
                "到達したため終了します。"
            )

            break

    else:
        raise RuntimeError(
            "最大ページ数に到達しました。"
            "サイト構造を確認してください。"
        )

    return diaries


# ========================================
# 2回目以降：新着だけ取得
# ========================================

def fetch_new_diaries(
    known_ids,
):
    new_diaries = []

    seen_ids = set()

    for page_number in range(
        1,
        MAX_PAGES + 1,
    ):
        page_entries = fetch_page(
            page_number
        )

        if not page_entries:
            break

        reached_known_entry = False

        for entry in page_entries:
            entry_id = entry["id"]

            if entry_id in known_ids:
                reached_known_entry = True
                break

            if entry_id in seen_ids:
                continue

            seen_ids.add(
                entry_id
            )

            new_diaries.append(
                entry
            )

        if reached_known_entry:
            print(
                "保存済みの記事に"
                "到達しました。"
            )

            break

    return new_diaries


# ========================================
# supplies.jsonへ保存
# ========================================

def save_supplies(supplies):
    unique_supplies = {}

    for supply in supplies:
        supply_id = supply.get(
            "id"
        )

        if not supply_id:
            continue

        unique_supplies[
            supply_id
        ] = supply

    result = list(
        unique_supplies.values()
    )


    # ====================================
    # 並び順
    # ====================================
    #
    # まず公開日で並べる。
    #
    # YouTube同士で同じ日なら
    # publishedAtによって
    # 公開時間順になる。
    #
    # Member Diaryには公開時刻が
    # ないため、同日内ではIDを
    # 補助的に使用する。

    result.sort(
        key=lambda item: (
            item.get(
                "date",
                "",
            ),
            item.get(
                "publishedAt",
                "",
            ),
            item.get(
                "id",
                "",
            ),
        )
    )


    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            result,
            file,
            ensure_ascii=False,
            indent=2,
        )

        file.write("\n")


# ========================================
# メイン処理
# ========================================

def main():
    existing_supplies = (
        load_existing_supplies()
    )

    existing_diaries = [
        supply
        for supply
        in existing_supplies
        if (
            supply.get("type")
            == "member_diary"
        )
    ]

    known_ids = {
        supply["id"]
        for supply
        in existing_diaries
        if supply.get("id")
    }

    print(
        "既存のMember Diary："
        f"{len(known_ids)}件"
    )


    # ====================================
    # 初回取得
    # ====================================

    if not known_ids:
        print(
            "初回取得："
            "過去のMember Diaryを"
            "取得します。"
        )

        diaries = (
            fetch_all_diaries()
        )

        if not diaries:
            raise RuntimeError(
                "Member Diaryを"
                "1件も取得できませんでした。"
                "サイト構造が変更された"
                "可能性があります。"
            )

        final_supplies = (
            existing_supplies
            + diaries
        )

        save_supplies(
            final_supplies
        )

        print(
            "初回取得完了："
            f"{len(diaries)}件"
        )

        return


    # ====================================
    # 差分取得
    # ====================================

    print(
        "差分取得："
        "新しいMember Diaryを"
        "確認します。"
    )

    new_diaries = (
        fetch_new_diaries(
            known_ids
        )
    )

    if not new_diaries:
        print(
            "新しいMember Diaryは"
            "ありません。"
        )

        return

    final_supplies = (
        existing_supplies
        + new_diaries
    )

    save_supplies(
        final_supplies
    )

    print(
        "新規Member Diary："
        f"{len(new_diaries)}件"
    )

    print(
        "supplies.jsonを"
        "更新しました。"
    )


if __name__ == "__main__":
    main()
