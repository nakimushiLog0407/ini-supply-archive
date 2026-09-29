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
LIST_URL = f"{BASE_URL}/blog/list/1/0/"

OUTPUT_FILE = "data/member_diary.json"
TEMP_FILE = OUTPUT_FILE + ".tmp"

REQUEST_INTERVAL = 0.5

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

    # HTMLタグを除去
    value = re.sub(
        r"<[^>]+>",
        "",
        value,
        flags=re.DOTALL,
    )

    # &#x1F62C; などを絵文字へ戻す
    value = html.unescape(value)

    # 改行・タブ・連続スペースを整理
    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


# ============================================================
# 1つの <li> から記事情報を取得
# ============================================================

def parse_article(li_html):
    # --------------------------------------------------------
    # 記事URL・記事ID
    # --------------------------------------------------------

    link_match = re.search(
        r'<a\b[^>]*'
        r'href=["\']'
        r'([^"\']*/blog/detail/(\d+)/?[^"\']*)'
        r'["\']',
        li_html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if not link_match:
        return None

    raw_url = html.unescape(
        link_match.group(1)
    )

    article_id = link_match.group(2)

    article_url = urllib.parse.urljoin(
        BASE_URL,
        raw_url,
    )

    # URLについている不要なクエリ等を除き、
    # 正規形に統一する
    article_url = (
        f"{BASE_URL}/blog/detail/"
        f"{article_id}/"
    )

    # --------------------------------------------------------
    # タイトル
    # --------------------------------------------------------

    title_match = re.search(
        r'<p\b[^>]*'
        r'class=["\'][^"\']*\btit\b[^"\']*["\']'
        r'[^>]*>'
        r'(.*?)'
        r'</p>',
        li_html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    title = (
        clean_text(title_match.group(1))
        if title_match
        else None
    )

    # --------------------------------------------------------
    # 公開日
    # --------------------------------------------------------

    date_match = re.search(
        r'<p\b[^>]*'
        r'class=["\'][^"\']*\bdate\b[^"\']*["\']'
        r'[^>]*>'
        r'(.*?)'
        r'</p>',
        li_html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    raw_date = (
        clean_text(date_match.group(1))
        if date_match
        else None
    )

    # --------------------------------------------------------
    # メンバー
    # --------------------------------------------------------

    member_match = re.search(
        r'<p\b[^>]*'
        r'class=["\'][^"\']*\bcategory\b[^"\']*'
        r'\buser\b[^"\']*["\']'
        r'[^>]*>'
        r'(.*?)'
        r'</p>',
        li_html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # classの順番が
    # "user category"
    # になった場合にも対応
    if not member_match:
        member_match = re.search(
            r'<p\b[^>]*'
            r'class=["\'][^"\']*\buser\b[^"\']*'
            r'\bcategory\b[^"\']*["\']'
            r'[^>]*>'
            r'(.*?)'
            r'</p>',
            li_html,
            flags=re.IGNORECASE | re.DOTALL,
        )

    member = (
        clean_text(member_match.group(1))
        if member_match
        else None
    )

    # --------------------------------------------------------
    # 必須項目チェック
    # --------------------------------------------------------

    missing = []

    if not title:
        missing.append("title")

    if not raw_date:
        missing.append("date")

    if not member:
        missing.append("member")

    if missing:
        raise ValueError(
            f"記事 {article_id}: "
            f"{', '.join(missing)} "
            "を取得できませんでした"
        )

    # --------------------------------------------------------
    # 日付を YYYY-MM-DD に統一
    # --------------------------------------------------------

    try:
        parsed_date = datetime.strptime(
            raw_date,
            "%Y.%m.%d",
        )

        normalized_date = parsed_date.strftime(
            "%Y-%m-%d"
        )

    except ValueError as error:
        raise ValueError(
            f"記事 {article_id}: "
            f"日付形式が不正です: {raw_date}"
        ) from error

    # --------------------------------------------------------
    # 完成データ
    # --------------------------------------------------------

    return {
        "id": f"member-diary-{article_id}",
        "type": "member_diary",
        "group": "fc",
        "date": normalized_date,
        "title": title,
        "member": member,
        "url": article_url,
    }


# ============================================================
# 一覧ページから <li> を取り出す
# ============================================================

def extract_article_blocks(page_html):
    # Member Diaryの記事一覧部分だけを対象にする
    list_match = re.search(
        r'<ul\b[^>]*'
        r'class=["\'][^"\']*'
        r'\blist--contents\b'
        r'[^"\']*["\']'
        r'[^>]*>'
        r'(.*?)'
        r'</ul>',
        page_html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if not list_match:
        raise RuntimeError(
            "Member Diaryの記事一覧 "
            "(ul.list--contents) "
            "を取得できませんでした。"
        )

    list_html = list_match.group(1)

    blocks = re.findall(
        r'<li\b[^>]*>'
        r'(.*?)'
        r'</li>',
        list_html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    return blocks


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

    url = f"{LIST_URL}?{query}"

    print(
        f"Member Diary "
        f"{page_number}ページ目を確認..."
    )

    page_html = fetch_html(url)

    blocks = extract_article_blocks(
        page_html
    )

    articles = []
    failures = []

    for block in blocks:
        # Member Diaryの記事リンクがない<li>は対象外
        if not re.search(
            r'/blog/detail/\d+/?',
            block,
            flags=re.IGNORECASE,
        ):
            continue

        try:
            article = parse_article(
                block
            )

            if article:
                articles.append(
                    article
                )

        except Exception as error:
            failures.append(
                str(error)
            )

    return articles, failures


# ============================================================
# 全ページ取得
# ============================================================

def fetch_all_diaries():
    all_articles = []
    all_failures = []

    seen_ids = set()

    page_number = 1

    while True:
        articles, failures = fetch_page(
            page_number
        )

        all_failures.extend(
            failures
        )

        # ----------------------------------------------------
        # 記事が0件なら最終ページを越えたと判断
        # ----------------------------------------------------

        if not articles and not failures:
            print(
                "記事のないページに到達しました。"
            )
            break

        new_count = 0

        for article in articles:
            article_id = article["id"]

            # ページネーション異常等で
            # 同じページが繰り返された場合の安全装置
            if article_id in seen_ids:
                continue

            seen_ids.add(
                article_id
            )

            all_articles.append(
                article
            )

            new_count += 1

        print(
            f"  {len(articles)}件取得"
        )

        # ----------------------------------------------------
        # 記事は存在するのに全件重複なら停止
        # ----------------------------------------------------

        if articles and new_count == 0:
            print(
                "既に取得済みの記事のみの"
                "ページに到達しました。"
            )
            break

        page_number += 1

        # 異常な無限ループ防止
        if page_number > 500:
            raise RuntimeError(
                "500ページを超えました。"
                "ページネーションに異常がある"
                "可能性があります。"
            )

        time.sleep(
            REQUEST_INTERVAL
        )

    # --------------------------------------------------------
    # 1件でも解析失敗したらJSONを更新しない
    # --------------------------------------------------------

    if all_failures:
        print()
        print(
            "=" * 60
        )
        print(
            "解析失敗した記事があります。"
        )
        print(
            "=" * 60
        )

        for failure in all_failures:
            print(
                f"- {failure}"
            )

        raise RuntimeError(
            f"{len(all_failures)}件の"
            "Member Diaryを解析できませんでした。"
            "member_diary.jsonは更新しません。"
        )

    # --------------------------------------------------------
    # 念のため0件も異常扱い
    # --------------------------------------------------------

    if not all_articles:
        raise RuntimeError(
            "Member Diaryを1件も"
            "取得できませんでした。"
            "member_diary.jsonは更新しません。"
        )

    # --------------------------------------------------------
    # 日付 → 記事ID の順で並べる
    #
    # 同日記事の場合、記事IDが大きい方を後にする。
    # --------------------------------------------------------

    def sort_key(article):
        article_number = int(
            article["id"].split("-")[-1]
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

    # まず一時ファイルへ完全に書き込む
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

        file.write("\n")

        file.flush()

        os.fsync(
            file.fileno()
        )

    # 書き込み成功後だけ本番ファイルを置換
    os.replace(
        TEMP_FILE,
        OUTPUT_FILE,
    )


# ============================================================
# メイン処理
# ============================================================

def main():
    print(
        "INI Member Diary の取得を開始します。"
    )
    print()

    try:
        diaries = fetch_all_diaries()

        print()
        print(
            f"全 {len(diaries)}件を"
            "正常に取得しました。"
        )

        save_diaries(
            diaries
        )

        print(
            f"{OUTPUT_FILE} を更新しました。"
        )

    except Exception:
        # 万が一.tmpが残っていたら削除
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
            "既存のmember_diary.jsonは"
            "変更していません。"
        )

        raise


if __name__ == "__main__":
    main()
