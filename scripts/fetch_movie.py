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

OUTPUT_FILE = "data/movie.json"
TEMP_FILE = OUTPUT_FILE + ".tmp"

REQUEST_INTERVAL = 0.5

# 異常な無限巡回を防ぐための上限
MAX_PAGES = 100


# ============================================================
# INI公式サイト上のMovieカテゴリ
#
# 取得時には各カテゴリを巡回するが、
# アプリ側ではカテゴリ分けしない。
# すべて「Movie」として保存する。
# ============================================================

MOVIE_LISTS = [
    {
        "name": "Message",
        "url": f"{BASE_URL}/movies/list/15/0/",
    },
    {
        "name": "Behind",
        "url": f"{BASE_URL}/movies/list/17/0/",
    },
    {
        "name": "Two-Shot INI",
        "url": f"{BASE_URL}/movies/list/19/0/",
    },
    {
        "name": "見えるラジオ",
        "url": f"{BASE_URL}/movies/list/23/0/",
    },
    {
        "name": "Others",
        "url": f"{BASE_URL}/movies/list/21/0/",
    },
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

    value = html.unescape(value)

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


# ============================================================
# Movieリンク抽出
#
# /movies/detail/123
# /movies/detail/123/
#
# の両方に対応
# ============================================================

def extract_movie_links(page_html):
    pattern = re.compile(
        r'<a\b'
        r'(?P<attributes>[^>]*?)'
        r'href=["\']'
        r'(?P<url>[^"\']*'
        r'/movies/detail/'
        r'(?P<id>\d+)'
        r'/?[^"\']*)'
        r'["\']'
        r'(?P<attributes_after>[^>]*)>'
        r'(?P<body>.*?)'
        r'</a>',
        flags=re.IGNORECASE | re.DOTALL,
    )

    results = []

    for match in pattern.finditer(page_html):
        results.append(
            {
                "movie_id": match.group("id"),
                "raw_url": match.group("url"),
                "body": match.group("body"),
            }
        )

    return results


# ============================================================
# classを持つ要素からテキスト取得
# ============================================================

def extract_text_by_class(
    block_html,
    class_names,
):
    if isinstance(class_names, str):
        class_names = [class_names]

    tag_pattern = re.compile(
        r'<(?P<tag>[a-zA-Z0-9]+)\b'
        r'(?P<attributes>[^>]*)>'
        r'(?P<body>.*?)'
        r'</(?P=tag)>',
        flags=re.IGNORECASE | re.DOTALL,
    )

    for match in tag_pattern.finditer(block_html):
        attributes = match.group(
            "attributes"
        )

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

        for class_name in class_names:
            if class_name in classes:
                text = clean_text(
                    match.group("body")
                )

                if text:
                    return text

    return None


# ============================================================
# 日付取得
# ============================================================

def extract_date_text(block_html):
    # よく使われるclass名を優先
    value = extract_text_by_class(
        block_html,
        [
            "date",
            "day",
            "time",
        ],
    )

    if value:
        date_match = re.search(
            r'\d{4}'
            r'[./-]'
            r'\d{1,2}'
            r'[./-]'
            r'\d{1,2}'
            r'\.?',
            value,
        )

        if date_match:
            return date_match.group(0)

    # class名に依存しない予備処理
    text = clean_text(block_html)

    if not text:
        return None

    date_match = re.search(
        r'\d{4}'
        r'[./-]'
        r'\d{1,2}'
        r'[./-]'
        r'\d{1,2}'
        r'\.?',
        text,
    )

    if date_match:
        return date_match.group(0)

    return None


# ============================================================
# タイトル取得
# ============================================================

def extract_title(block_html):
    title = extract_text_by_class(
        block_html,
        [
            "tit",
            "title",
        ],
    )

    if title:
        return title

    # 見出しタグも確認
    heading_pattern = re.compile(
        r'<h[1-6]\b[^>]*>'
        r'(.*?)'
        r'</h[1-6]>',
        flags=re.IGNORECASE | re.DOTALL,
    )

    match = heading_pattern.search(
        block_html
    )

    if match:
        value = clean_text(
            match.group(1)
        )

        if value:
            return value

    return None


# ============================================================
# 日付を YYYY-MM-DD に統一
# ============================================================

def normalize_date(
    raw_date,
    movie_id,
):
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
        f"Movie {movie_id}: "
        f"日付形式を解析できません: "
        f"{raw_date}"
    )


# ============================================================
# Movie 1件を解析
# ============================================================

def parse_movie(movie_link):
    movie_id = movie_link["movie_id"]
    body = movie_link["body"]

    title = extract_title(body)
    raw_date = extract_date_text(body)

    missing = []

    if not title:
        missing.append("title")

    if not raw_date:
        missing.append("date")

    if missing:
        raise ValueError(
            f"Movie {movie_id}: "
            f"{', '.join(missing)} "
            "を取得できませんでした"
        )

    normalized_date = normalize_date(
        raw_date,
        movie_id,
    )

    movie_url = (
        f"{BASE_URL}/movies/detail/"
        f"{movie_id}"
    )

    return {
        "id": f"movie-{movie_id}",
        "type": "movie",
        "group": "fc",
        "date": normalized_date,
        "title": title,
        "url": movie_url,
    }


# ============================================================
# 一覧ページ1ページ分を解析
# ============================================================

def parse_page(
    page_html,
    category_name,
    page_number,
):
    movie_links = extract_movie_links(
        page_html
    )

    print(
        "  検出："
        f"Movieリンク {len(movie_links)}件"
    )

    if not movie_links:
        return [], []

    # 同じMovieへのリンクが
    # ページ内に複数ある場合に備える
    grouped = {}

    for movie_link in movie_links:
        movie_id = movie_link["movie_id"]

        grouped.setdefault(
            movie_id,
            [],
        ).append(movie_link)

    movies = []
    failures = []

    for movie_id, candidates in grouped.items():
        parsed = None
        last_error = None

        for candidate in candidates:
            try:
                parsed = parse_movie(
                    candidate
                )
                break

            except ValueError as error:
                last_error = error

        if parsed:
            movies.append(parsed)

        else:
            if last_error:
                message = str(last_error)
            else:
                message = (
                    f"Movie {movie_id}: "
                    "解析できませんでした"
                )

            failures.append(
                {
                    "category": category_name,
                    "page": page_number,
                    "movie_id": movie_id,
                    "message": message,
                }
            )

    return movies, failures


# ============================================================
# 一覧ページ1ページを取得
# ============================================================

def fetch_page(
    category_name,
    list_url,
    page_number,
):
    query = urllib.parse.urlencode(
        {
            "page": page_number,
        }
    )

    url = f"{list_url}?{query}"

    print(
        f"{category_name} "
        f"{page_number}ページ目を確認..."
    )

    page_html = fetch_html(url)

    movies, failures = parse_page(
        page_html,
        category_name,
        page_number,
    )

    print(
        f"  {len(movies)}件取得"
    )

    if failures:
        for failure in failures:
            print(
                "  警告："
                f"{failure['message']}"
            )

    return movies, failures


# ============================================================
# 1カテゴリを最終ページまで取得
# ============================================================

def fetch_category(
    category_name,
    list_url,
):
    all_movies = []
    all_failures = []

    seen_ids = set()
    previous_page_ids = None

    for page_number in range(
        1,
        MAX_PAGES + 1,
    ):
        movies, failures = fetch_page(
            category_name,
            list_url,
            page_number,
        )

        all_failures.extend(failures)

        # Movieも解析失敗も0件なら
        # 最終ページを越えたと判断
        if not movies and not failures:
            print(
                f"{category_name}: "
                "Movieのないページに"
                "到達しました。"
            )
            break

        current_page_ids = {
            movie["id"]
            for movie in movies
        }

        # ページ番号が無視され、
        # 同じページが返され続けた場合の安全装置
        if (
            previous_page_ids is not None
            and current_page_ids
            == previous_page_ids
            and not failures
        ):
            raise RuntimeError(
                f"{category_name}: "
                f"{page_number}ページ目が"
                "直前のページと完全に同じです。"
                "ページネーションを"
                "正常に取得できていない"
                "可能性があります。"
            )

        previous_page_ids = (
            current_page_ids
        )

        for movie in movies:
            movie_id = movie["id"]

            if movie_id in seen_ids:
                continue

            seen_ids.add(movie_id)
            all_movies.append(movie)

        time.sleep(REQUEST_INTERVAL)

    else:
        raise RuntimeError(
            f"{category_name}: "
            f"{MAX_PAGES}ページまで"
            "到達しました。"
            "最終ページを"
            "検出できませんでした。"
        )

    return all_movies, all_failures


# ============================================================
# 全カテゴリ取得
# ============================================================

def fetch_all_movies():
    all_failures = []

    # Movie IDをカテゴリ横断で重複排除
    movies_by_id = {}

    for category in MOVIE_LISTS:
        print()
        print("=" * 60)
        print(
            f"{category['name']} を取得"
        )
        print("=" * 60)

        (
            category_movies,
            category_failures,
        ) = fetch_category(
            category["name"],
            category["url"],
        )

        all_failures.extend(
            category_failures
        )

        for movie in category_movies:
            movie_id = movie["id"]

            if movie_id in movies_by_id:
                continue

            movies_by_id[movie_id] = movie

        time.sleep(REQUEST_INTERVAL)

    # 解析失敗が1件でもあれば保存しない
    if all_failures:
        print()
        print("=" * 60)
        print("解析失敗したMovie")
        print("=" * 60)

        for failure in all_failures:
            print(
                f"カテゴリ "
                f"{failure['category']} / "
                f"ページ "
                f"{failure['page']} / "
                f"Movie "
                f"{failure['movie_id']} / "
                f"{failure['message']}"
            )

        print("=" * 60)

        raise RuntimeError(
            f"{len(all_failures)}件の"
            "Movieを解析できませんでした。"
            "movie.jsonは更新しません。"
        )

    all_movies = list(
        movies_by_id.values()
    )

    # 古い順
    # 同日はMovie IDの数字順
    all_movies.sort(
        key=lambda movie: (
            movie.get(
                "date",
                "",
            ),
            int(
                movie["id"].replace(
                    "movie-",
                    "",
                )
            ),
        )
    )

    return all_movies


# ============================================================
# 既存JSON読み込み
# ============================================================

def load_existing_movies():
    if not os.path.exists(OUTPUT_FILE):
        return []

    with open(
        OUTPUT_FILE,
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError(
            f"{OUTPUT_FILE} の"
            "形式が不正です。"
        )

    return data


# ============================================================
# JSONを安全に保存
# ============================================================

def save_movies(movies):
    os.makedirs(
        os.path.dirname(OUTPUT_FILE),
        exist_ok=True,
    )

    with open(
        TEMP_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            movies,
            file,
            ensure_ascii=False,
            indent=2,
        )

        file.write("\n")

    # 一時ファイルを再度読み込み、
    # 正しいJSONになっているか確認
    with open(
        TEMP_FILE,
        "r",
        encoding="utf-8",
    ) as file:
        verification = json.load(file)

    if not isinstance(
        verification,
        list,
    ):
        raise RuntimeError(
            "保存前検証に失敗しました。"
        )

    os.replace(
        TEMP_FILE,
        OUTPUT_FILE,
    )


# ============================================================
# メイン処理
# ============================================================

def main():
    print(
        "INI Movie取得を開始します。"
    )

    print()

    existing_movies = (
        load_existing_movies()
    )

    print(
        "既存Movie："
        f"{len(existing_movies)}件"
    )

    movies = fetch_all_movies()

    print()
    print("=" * 60)
    print("取得結果")
    print("=" * 60)

    print(
        "公式サイト上のMovie："
        f"{len(movies)}件"
    )

    existing_ids = {
        movie.get("id")
        for movie in existing_movies
        if movie.get("id")
    }

    current_ids = {
        movie.get("id")
        for movie in movies
        if movie.get("id")
    }

    new_ids = (
        current_ids
        - existing_ids
    )

    removed_ids = (
        existing_ids
        - current_ids
    )

    print(
        "新規Movie："
        f"{len(new_ids)}件"
    )

    if removed_ids:
        print(
            "既存JSONにのみ存在："
            f"{len(removed_ids)}件"
        )

        for movie_id in sorted(
            removed_ids
        ):
            print(
                f"  {movie_id}"
            )

    # 0件なら異常と判断し、
    # 既存JSONを空データで上書きしない
    if not movies:
        raise RuntimeError(
            "Movieを1件も"
            "取得できませんでした。"
            "movie.jsonは更新しません。"
        )

    save_movies(movies)

    print()
    print(
        f"{OUTPUT_FILE} を"
        f"{len(movies)}件で更新しました。"
    )


if __name__ == "__main__":
    try:
        main()

    except Exception:
        # 異常終了時に.tmpが残った場合は削除
        if os.path.exists(TEMP_FILE):
            try:
                os.remove(TEMP_FILE)
            except OSError:
                pass

        raise
