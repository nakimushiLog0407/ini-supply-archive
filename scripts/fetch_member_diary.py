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
LIST_URL = "https://ini-official.com/blog/list/1/0/"

# Member Diary専用ファイル
OUTPUT_FILE = Path("data/member_diary.json")

USER_AGENT = (
    "Mozilla/5.0 "
    "(Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/140.0.0.0 Safari/537.36"
)

# 無限ループ防止
MAX_PAGES = 200


# ========================================
# HTML取得
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
            response.headers.get_content_charset()
            or "utf-8"
        )

        return response.read().decode(
            charset,
            errors="replace",
        )


# ========================================
# HTML → プレーンテキスト
# ========================================

def clean_text(value):
    # script / styleを除去
    value = re.sub(
        r"<script\b[^>]*>.*?</script>",
        " ",
        value,
        flags=re.IGNORECASE | re.DOTALL,
    )

    value = re.sub(
        r"<style\b[^>]*>.*?</style>",
        " ",
        value,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # brを空白へ
    value = re.sub(
        r"<br\s*/?>",
        " ",
        value,
        flags=re.IGNORECASE,
    )

    # HTMLタグを除去
    value = re.sub(
        r"<[^>]+>",
        " ",
        value,
    )

    # HTMLエンティティを戻す
    value = html.unescape(value)

    # 空白整理
    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


# ========================================
# 既存データ読み込み
# ========================================

def load_existing_diaries():
    if not OUTPUT_FILE.exists():
        return []

    with OUTPUT_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise RuntimeError(
            "data/member_diary.json の形式が"
            "配列ではありません。"
        )

    return data


# ========================================
# URLを絶対URL化
# ========================================

def make_absolute_url(url):
    return urllib.parse.urljoin(
        BASE_URL,
        html.unescape(url),
    )


# ========================================
# 公開日抽出
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

    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))

    normalized = (
        f"{year:04d}-"
        f"{month:02d}-"
        f"{day:02d}"
    )

    return normalized, match


# ========================================
# article ID取得
# ========================================

def extract_article_id(url):
    match = re.search(
        r"/blog/detail/(\d+)/?",
        url,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    return match.group(1)


# ========================================
# 記事リンク候補を取得
# ========================================

def extract_article_candidates(page_html):
    pattern = re.compile(
        r"<a\b"
        r"(?P<attrs>[^>]*?)"
        r"href=[\"']"
        r"(?P<url>[^\"']*"
        r"/blog/detail/\d+/?"
        r"[^\"']*)"
        r"[\"']"
        r"(?P<attrs2>[^>]*)>"
        r"(?P<body>.*?)"
        r"</a>",
        flags=re.IGNORECASE | re.DOTALL,
    )

    candidates = []

    for match in pattern.finditer(page_html):
        url = make_absolute_url(
            match.group("url")
        )

        article_id = extract_article_id(url)

        if not article_id:
            continue

        body_html = match.group("body")
        body_text = clean_text(body_html)

        candidates.append(
            {
                "article_id": article_id,
                "url": url,
                "body_html": body_html,
                "body_text": body_text,
                "start": match.start(),
                "end": match.end(),
            }
        )

    return candidates


# ========================================
# 記事周辺HTML取得
# ========================================

def get_context_html(
    page_html,
    candidate,
    radius=5000,
):
    start = max(
        0,
        candidate["start"] - radius,
    )

    end = min(
        len(page_html),
        candidate["end"] + radius,
    )

    return page_html[start:end]


# ========================================
# タイトル・日付・メンバーを
# テキストから解析
# ========================================

def parse_text_metadata(text):
    date, date_match = extract_date(text)

    if not date or not date_match:
        return None

    before = text[
        :date_match.start()
    ].strip()

    after = text[
        date_match.end():
    ].strip()

    if not before or not after:
        return None

    return {
        "date": date,
        "before": before,
        "after": after,
    }


# ========================================
# リンク本文から直接解析
# ========================================

def parse_from_link_body(candidate):
    text = candidate["body_text"]

    if not text:
        return None

    metadata = parse_text_metadata(text)

    if not metadata:
        return None

    title = metadata["before"].strip()
    member = metadata["after"].strip()

    if not title or not member:
        return None

    return {
        "title": title,
        "member": member,
        "date": metadata["date"],
    }


# ========================================
# 周辺HTMLから解析
# ========================================

def parse_from_context(
    page_html,
    candidate,
):
    context_html = get_context_html(
        page_html,
        candidate,
    )

    context_text = clean_text(
        context_html
    )

    # 日付をすべて探す
    date_matches = list(
        re.finditer(
            r"(20\d{2})"
            r"[./-]"
            r"(\d{1,2})"
            r"[./-]"
            r"(\d{1,2})",
            context_text,
        )
    )

    if not date_matches:
        return None

    # リンク本文にタイトル文字列がある場合は、
    # そのタイトルに最も近い日付を使用する
    link_text = candidate[
        "body_text"
    ].strip()

    if link_text:
        title_position = (
            context_text.find(link_text)
        )
    else:
        title_position = -1

    if title_position >= 0:
        date_match = min(
            date_matches,
            key=lambda item: abs(
                item.start()
                - title_position
            ),
        )
    else:
        # タイトル文字列がリンク内にない場合は
        # コンテキスト中央に最も近い日付
        center = len(context_text) // 2

        date_match = min(
            date_matches,
            key=lambda item: abs(
                item.start() - center
            ),
        )

    year = int(date_match.group(1))
    month = int(date_match.group(2))
    day = int(date_match.group(3))

    date = (
        f"{year:04d}-"
        f"{month:02d}-"
        f"{day:02d}"
    )

    # 日付の前後を必要な範囲だけ取得
    before = context_text[
        max(
            0,
            date_match.start() - 500,
        ):
        date_match.start()
    ].strip()

    after = context_text[
        date_match.end():
        min(
            len(context_text),
            date_match.end() + 300,
        )
    ].strip()

    # ====================================
    # タイトル
    # ====================================

    # リンク本文にテキストがあるなら
    # それを最優先
    title = link_text

    # リンク本文が画像だけ等の場合は、
    # 日付直前のテキストを候補にする
    if not title:
        # 直前の文章の最後側を利用
        pieces = [
            piece.strip()
            for piece in re.split(
                r"\s{2,}",
                before,
            )
            if piece.strip()
        ]

        if pieces:
            title = pieces[-1]

    if not title:
        return None


    # ====================================
    # メンバー名
    # ====================================

    # 日付直後のテキストから
    # 最初のまとまりを取得
    member = after

    # ページ上の区切りになりやすい文字で
    # 後続情報を切る
    member = re.split(
        r"(?:\||｜)",
        member,
        maxsplit=1,
    )[0].strip()

    # 改行等が既に空白になっているため、
    # 長すぎる場合は最初の適度な範囲にする
    if len(member) > 80:
        member = member[:80].strip()

    if not member:
        return None

    return {
        "title": title,
        "member": member,
        "date": date,
    }


# ========================================
# 1記事を解析
# ========================================

def parse_candidate(
    page_html,
    candidate,
):
    # まずリンク要素だけで解析
    metadata = parse_from_link_body(
        candidate
    )

    # 取れなければ周辺HTMLを見る
    if not metadata:
        metadata = parse_from_context(
            page_html,
            candidate,
        )

    if not metadata:
        return None

    return {
        "id": (
            "member-diary-"
            + candidate["article_id"]
        ),
        "type": "member_diary",
        "group": "fc",
        "date": metadata["date"],
        "title": metadata["title"],
        "member": metadata["member"],
        "url": candidate["url"],
    }


# ========================================
# 一覧ページ解析
# ========================================

def parse_diary_entries(
    page_html,
    page_number,
):
    candidates = (
        extract_article_candidates(
            page_html
        )
    )

    if not candidates:
        return [], []


    # 同じ記事へのリンクが複数ある場合があるため
    # article ID単位で候補をまとめる
    grouped = {}

    for candidate in candidates:
        article_id = candidate[
            "article_id"
        ]

        grouped.setdefault(
            article_id,
            [],
        ).append(candidate)


    entries = []
    failures = []


    for article_id, article_candidates in (
        grouped.items()
    ):
        parsed = None

        # 同じ記事への複数リンクを順番に試す
        for candidate in article_candidates:
            parsed = parse_candidate(
                page_html,
                candidate,
            )

            if parsed:
                break

        if parsed:
            entries.append(parsed)

        else:
            failures.append(
                {
                    "page": page_number,
                    "article_id":
                        article_id,
                }
            )

            print(
                "  警告："
                f"記事 {article_id} の"
                "情報を解析できませんでした。"
            )


    return entries, failures


# ========================================
# 指定ページ取得
# ========================================

def fetch_page(page_number):
    query = urllib.parse.urlencode(
        {
            "page": page_number,
            "writer": 0,
        }
    )

    url = f"{LIST_URL}?{query}"

    print(
        "Member Diary "
        f"{page_number}ページ目を確認..."
    )

    page_html = fetch_html(url)

    entries, failures = (
        parse_diary_entries(
            page_html,
            page_number,
        )
    )

    print(
        f"  {len(entries)}件取得"
    )

    return entries, failures


# ========================================
# 初回全件取得
# ========================================

def fetch_all_diaries():
    diaries = []

    all_failures = []

    seen_ids = set()


    for page_number in range(
        1,
        MAX_PAGES + 1,
    ):
        page_entries, failures = (
            fetch_page(page_number)
        )

        all_failures.extend(
            failures
        )


        # 記事そのものがないページ
        if (
            not page_entries
            and not failures
        ):
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


        # 解析失敗もなく、
        # 新しい記事もない場合は終了
        if (
            new_count == 0
            and not failures
        ):
            print(
                "新しい記事がないため"
                "終了します。"
            )

            break

    else:
        raise RuntimeError(
            "最大ページ数に到達しました。"
            "ページ構造を確認してください。"
        )


    # ====================================
    # 取りこぼしチェック
    # ====================================

    if all_failures:
        print("")
        print(
            "===== 解析失敗記事 ====="
        )

        for failure in all_failures:
            print(
                "ページ "
                f"{failure['page']} / "
                "記事 "
                f"{failure['article_id']}"
            )

        print(
            "========================"
        )

        raise RuntimeError(
            f"{len(all_failures)}件の"
            "Member Diaryを"
            "解析できませんでした。"
            "member_diary.jsonは"
            "更新しません。"
        )


    return diaries


# ========================================
# 差分取得
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
        page_entries, failures = (
            fetch_page(page_number)
        )


        # 差分取得でも解析失敗を
        # 黙って無視しない
        if failures:
            failure_ids = ", ".join(
                failure["article_id"]
                for failure in failures
            )

            raise RuntimeError(
                "Member Diaryの解析に"
                "失敗しました。"
                f" page={page_number}, "
                f"article={failure_ids}"
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
# 保存
# ========================================

def save_diaries(diaries):
    unique = {}

    for diary in diaries:
        diary_id = diary.get("id")

        if not diary_id:
            continue

        unique[diary_id] = diary


    result = list(
        unique.values()
    )


    # 日付 → 記事IDで並べる
    #
    # Member Diaryには公開時刻がないため
    # 同日内の厳密な時刻順は付けない
    def sort_key(item):
        article_id_match = re.search(
            r"(\d+)$",
            item.get("id", ""),
        )

        article_number = (
            int(article_id_match.group(1))
            if article_id_match
            else 0
        )

        return (
            item.get("date", ""),
            article_number,
        )


    result.sort(
        key=sort_key
    )


    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    # 一度一時ファイルへ書く
    # → 正常に書けた場合だけ置き換える
    temp_file = OUTPUT_FILE.with_suffix(
        ".json.tmp"
    )


    with temp_file.open(
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


    temp_file.replace(
        OUTPUT_FILE
    )


# ========================================
# メイン
# ========================================

def main():
    existing_diaries = (
        load_existing_diaries()
    )


    known_ids = {
        diary["id"]
        for diary in existing_diaries
        if diary.get("id")
    }


    print(
        "既存のMember Diary："
        f"{len(known_ids)}件"
    )


    # ====================================
    # 初回
    # ====================================

    if not known_ids:
        print(
            "初回取得："
            "Member Diaryを"
            "最古の記事まで取得します。"
        )


        diaries = (
            fetch_all_diaries()
        )


        if not diaries:
            raise RuntimeError(
                "Member Diaryを"
                "1件も取得できませんでした。"
            )


        save_diaries(
            diaries
        )


        print("")
        print(
            "初回取得完了："
            f"{len(diaries)}件"
        )

        print(
            "data/member_diary.json "
            "を作成しました。"
        )

        return


    # ====================================
    # 2回目以降
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


    final_diaries = (
        existing_diaries
        + new_diaries
    )


    save_diaries(
        final_diaries
    )


    print("")
    print(
        "新規Member Diary："
        f"{len(new_diaries)}件"
    )

    print(
        "data/member_diary.json "
        "を更新しました。"
    )


if __name__ == "__main__":
    main()
