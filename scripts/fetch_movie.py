import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime
from html.parser import HTMLParser


# ============================================================
# 設定
# ============================================================

BASE_URL = "https://ini-official.com"

OUTPUT_FILE = "data/movie.json"
TEMP_FILE = OUTPUT_FILE + ".tmp"

REQUEST_INTERVAL = 0.5

# ページネーション異常時の無限巡回防止
MAX_PAGES = 100


# ============================================================
# INI公式サイト上のMovieカテゴリ
#
# 取得時には各カテゴリを巡回する。
# アプリ側ではカテゴリ分けせず、
# すべて「Movie」として統合する。
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
# テキスト整形
# ============================================================

def clean_text(value):
    if value is None:
        return None

    value = html.unescape(value)

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    value = value.strip()

    return value or None


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
# サムネイルURL取得
#
# 実際のHTML：
#
# <figure class="thumb">
#   <img
#     ...
#     style="background-image: url(/static2/...jpeg)"
#     alt="タイトル"
#   >
# </figure>
#
# src は blank_thumb.gif のため使用しない。
# background-image のURLを使用する。
# ============================================================

def extract_background_image(style_value):
    if not style_value:
        return None

    match = re.search(
        r'background-image\s*:\s*'
        r'url\(\s*'
        r'["\']?'
        r'([^)"\']+)'
        r'["\']?'
        r'\s*\)',
        style_value,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    raw_url = match.group(1).strip()

    return urllib.parse.urljoin(
        BASE_URL,
        raw_url,
    )


# ============================================================
# Movie一覧HTMLパーサー
#
# 診断で確認した実際の構造：
#
# <li>
#   <a href="/movies/detail/589">
#     <figure class="thumb">
#       <img
#         style="background-image: url(...)"
#         alt="..."
#       >
#     </figure>
#
#     <div class="list__txt">
#       <p class="tit">タイトル</p>
#       <p class="date">2026.07.18</p>
#     </div>
#   </a>
# </li>
# ============================================================

class MovieListParser(HTMLParser):

    def __init__(self):
        super().__init__(
            convert_charrefs=True
        )

        self.movies = []

        # 現在解析中のMovie
        self.current_movie = None

        # Movieリンク内にいる深さ
        self.movie_link_depth = 0

        # tit / date の取得状態
        self.capture_title = False
        self.capture_date = False

        self.title_parts = []
        self.date_parts = []


    # --------------------------------------------------------
    # class属性をsetに変換
    # --------------------------------------------------------

    @staticmethod
    def get_classes(attrs_dict):
        class_value = attrs_dict.get(
            "class",
            "",
        )

        return set(
            class_value.split()
        )


    # --------------------------------------------------------
    # 開始タグ
    # --------------------------------------------------------

    def handle_starttag(
        self,
        tag,
        attrs,
    ):
        attrs_dict = dict(attrs)

        # ====================================================
        # Movie個別リンクを検出
        # ====================================================

        if (
            tag.lower() == "a"
            and self.current_movie is None
        ):
            href = attrs_dict.get(
                "href",
                "",
            )

            match = re.search(
                r'/movies/detail/(\d+)/?',
                href,
                flags=re.IGNORECASE,
            )

            if match:
                movie_id = match.group(1)

                self.current_movie = {
                    "movie_id": movie_id,
                    "href": href,
                    "title": None,
                    "date": None,
                    "thumbnail": None,
                    "alt_title": None,
                }

                self.movie_link_depth = 1

                self.capture_title = False
                self.capture_date = False

                self.title_parts = []
                self.date_parts = []

                return

        # Movieリンクの外なら以降は不要
        if self.current_movie is None:
            return

        # ----------------------------------------------------
        # Movieリンク内部のタグ階層を追跡
        # ----------------------------------------------------

        if tag.lower() == "a":
            self.movie_link_depth += 1

        classes = self.get_classes(
            attrs_dict
        )

        # ====================================================
        # <p class="tit">
        # ====================================================

        if (
            tag.lower() == "p"
            and "tit" in classes
        ):
            self.capture_title = True
            self.title_parts = []

        # ====================================================
        # <p class="date">
        # ====================================================

        elif (
            tag.lower() == "p"
            and "date" in classes
        ):
            self.capture_date = True
            self.date_parts = []

        # ====================================================
        # <img>
        #
        # style の background-image から
        # サムネイルURLを取得
        #
        # alt はタイトルの予備取得元として保存
        # ====================================================

        elif tag.lower() == "img":
            style_value = attrs_dict.get(
                "style"
            )

            thumbnail = (
                extract_background_image(
                    style_value
                )
            )

            if thumbnail:
                self.current_movie[
                    "thumbnail"
                ] = thumbnail

            alt_value = clean_text(
                attrs_dict.get("alt")
            )

            if alt_value:
                self.current_movie[
                    "alt_title"
                ] = alt_value


    # --------------------------------------------------------
    # テキスト
    # --------------------------------------------------------

    def handle_data(self, data):
        if self.current_movie is None:
            return

        if self.capture_title:
            self.title_parts.append(
                data
            )

        if self.capture_date:
            self.date_parts.append(
                data
            )


    # --------------------------------------------------------
    # 終了タグ
    # --------------------------------------------------------

    def handle_endtag(self, tag):
        if self.current_movie is None:
            return

        tag_lower = tag.lower()

        # ====================================================
        # title終了
        # ====================================================

        if (
            tag_lower == "p"
            and self.capture_title
        ):
            title = clean_text(
                "".join(
                    self.title_parts
                )
            )

            if title:
                self.current_movie[
                    "title"
                ] = title

            self.capture_title = False
            self.title_parts = []

            return

        # ====================================================
        # date終了
        # ====================================================

        if (
            tag_lower == "p"
            and self.capture_date
        ):
            date_value = clean_text(
                "".join(
                    self.date_parts
                )
            )

            if date_value:
                self.current_movie[
                    "date"
                ] = date_value

            self.capture_date = False
            self.date_parts = []

            return

        # ====================================================
        # Movieリンク終了
        # ====================================================

        if tag_lower == "a":
            self.movie_link_depth -= 1

            if self.movie_link_depth <= 0:
                self.movies.append(
                    self.current_movie
                )

                self.current_movie = None

                self.movie_link_depth = 0

                self.capture_title = False
                self.capture_date = False

                self.title_parts = []
                self.date_parts = []


# ============================================================
# 1ページからMovie候補を取得
# ============================================================

def parse_movie_candidates(page_html):
    parser = MovieListParser()

    parser.feed(
        page_html
    )

    parser.close()

    return parser.movies


# ============================================================
# Movie 1件を正式なJSONデータへ変換
# ============================================================

def build_movie(candidate):
    movie_id = candidate[
        "movie_id"
    ]

    title = clean_text(
        candidate.get("title")
    )

    alt_title = clean_text(
        candidate.get("alt_title")
    )

    raw_date = clean_text(
        candidate.get("date")
    )

    thumbnail = clean_text(
        candidate.get("thumbnail")
    )

    # --------------------------------------------------------
    # タイトル
    #
    # 第一候補：
    # <p class="tit">
    #
    # 第二候補：
    # <img alt="...">
    # --------------------------------------------------------

    if not title:
        title = alt_title

    missing = []

    if not title:
        missing.append(
            "title"
        )

    if not raw_date:
        missing.append(
            "date"
        )

    if not thumbnail:
        missing.append(
            "thumbnail"
        )

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

    movie_url = urllib.parse.urljoin(
        BASE_URL,
        candidate["href"],
    )

    return {
        "id": f"movie-{movie_id}",
        "type": "movie",
        "group": "fc",
        "date": normalized_date,
        "title": title,
        "thumbnail": thumbnail,
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
    candidates = (
        parse_movie_candidates(
            page_html
        )
    )

    print(
        "  検出："
        f"Movieリンク "
        f"{len(candidates)}件"
    )

    if not candidates:
        return [], []

    # --------------------------------------------------------
    # 同じMovie IDがページ内に複数存在しても
    # 1件として扱う
    # --------------------------------------------------------

    candidates_by_id = {}

    for candidate in candidates:
        movie_id = candidate[
            "movie_id"
        ]

        if movie_id not in candidates_by_id:
            candidates_by_id[
                movie_id
            ] = candidate

    movies = []
    failures = []

    for (
        movie_id,
        candidate,
    ) in candidates_by_id.items():

        try:
            movie = build_movie(
                candidate
            )

            movies.append(
                movie
            )

        except ValueError as error:
            failures.append(
                {
                    "category":
                        category_name,
                    "page":
                        page_number,
                    "movie_id":
                        movie_id,
                    "message":
                        str(error),
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

    url = (
        f"{list_url}?{query}"
    )

    print(
        f"{category_name} "
        f"{page_number}ページ目を確認..."
    )

    page_html = fetch_html(
        url
    )

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
        (
            movies,
            failures,
        ) = fetch_page(
            category_name,
            list_url,
            page_number,
        )

        all_failures.extend(
            failures
        )

        # ----------------------------------------------------
        # Movieも解析失敗も0件
        #
        # → 最終ページを越えたと判断
        # ----------------------------------------------------

        if (
            not movies
            and not failures
        ):
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

        # ----------------------------------------------------
        # ページ番号を無視して
        # 同じページが返され続ける場合の安全装置
        # ----------------------------------------------------

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
            movie_id = movie[
                "id"
            ]

            if movie_id in seen_ids:
                continue

            seen_ids.add(
                movie_id
            )

            all_movies.append(
                movie
            )

        time.sleep(
            REQUEST_INTERVAL
        )

    else:
        raise RuntimeError(
            f"{category_name}: "
            f"{MAX_PAGES}ページまで"
            "到達しました。"
            "最終ページを"
            "検出できませんでした。"
        )

    return (
        all_movies,
        all_failures,
    )


# ============================================================
# 全カテゴリ取得
# ============================================================

def fetch_all_movies():
    all_failures = []

    # Movie IDをカテゴリ横断で重複排除
    movies_by_id = {}

    for category in MOVIE_LISTS:
        print()
        print(
            "=" * 60
        )

        print(
            f"{category['name']} を取得"
        )

        print(
            "=" * 60
        )

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
            movie_id = movie[
                "id"
            ]

            if movie_id in movies_by_id:
                continue

            movies_by_id[
                movie_id
            ] = movie

        time.sleep(
            REQUEST_INTERVAL
        )

    # --------------------------------------------------------
    # 解析失敗が1件でもあれば保存しない
    # --------------------------------------------------------

    if all_failures:
        print()
        print(
            "=" * 60
        )

        print(
            "解析失敗したMovie"
        )

        print(
            "=" * 60
        )

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

        print(
            "=" * 60
        )

        raise RuntimeError(
            f"{len(all_failures)}件の"
            "Movieを解析できませんでした。"
            "movie.jsonは更新しません。"
        )

    all_movies = list(
        movies_by_id.values()
    )

    # --------------------------------------------------------
    # 古い順
    #
    # 同日はMovie IDの数字順
    # --------------------------------------------------------

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
    if not os.path.exists(
        OUTPUT_FILE
    ):
        return []

    with open(
        OUTPUT_FILE,
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(
            file
        )

    if not isinstance(
        data,
        list,
    ):
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
        os.path.dirname(
            OUTPUT_FILE
        ),
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

        file.write(
            "\n"
        )

    # --------------------------------------------------------
    # 一時ファイルを再読み込みして
    # 正しいJSONであることを確認
    # --------------------------------------------------------

    with open(
        TEMP_FILE,
        "r",
        encoding="utf-8",
    ) as file:
        verification = json.load(
            file
        )

    if not isinstance(
        verification,
        list,
    ):
        raise RuntimeError(
            "保存前検証に失敗しました。"
        )

    if len(
        verification
    ) != len(
        movies
    ):
        raise RuntimeError(
            "保存前検証で"
            "Movie件数が一致しません。"
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
    print(
        "=" * 60
    )

    print(
        "取得結果"
    )

    print(
        "=" * 60
    )

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

    # --------------------------------------------------------
    # 0件取得は異常
    #
    # 既存JSONを空データで上書きしない
    # --------------------------------------------------------

    if not movies:
        raise RuntimeError(
            "Movieを1件も"
            "取得できませんでした。"
            "movie.jsonは更新しません。"
        )

    # --------------------------------------------------------
    # 全件に必須項目が存在することを最終確認
    # --------------------------------------------------------

    required_fields = [
        "id",
        "type",
        "group",
        "date",
        "title",
        "thumbnail",
        "url",
    ]

    for movie in movies:
        missing_fields = [
            field
            for field in required_fields
            if not movie.get(field)
        ]

        if missing_fields:
            raise RuntimeError(
                f"{movie.get('id', 'unknown')}: "
                f"{', '.join(missing_fields)} "
                "がありません。"
                "movie.jsonは更新しません。"
            )

    save_movies(
        movies
    )

    print()
    print(
        f"{OUTPUT_FILE} を"
        f"{len(movies)}件で更新しました。"
    )


if __name__ == "__main__":
    try:
        main()

    except Exception:
        # 異常終了時に.tmpが残っていたら削除
        if os.path.exists(
            TEMP_FILE
        ):
            try:
                os.remove(
                    TEMP_FILE
                )

            except OSError:
                pass

        raise
