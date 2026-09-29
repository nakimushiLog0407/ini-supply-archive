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
# 各カテゴリを巡回して過去データを取得する。
#
# ただし、カテゴリにまだ属していないMovieが
# LATEST MOVIEにだけ掲載される場合があるため、
# MOVIE_TOP_URL も別途取得する。
#
# アプリ側ではカテゴリ分けせず、
# すべて「Movie」として統合する。
# ============================================================

MOVIE_TOP_URL = (
    f"{BASE_URL}/movies/category/"
)


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
            "Accept-Language":
                "ja,en-US;q=0.9,en;q=0.8",
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
# 実際のHTMLでは src が blank_thumb.gif の場合があるため、
# style の background-image を使用する。
# ============================================================

def extract_background_image(
    style_value
):
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

    raw_url = (
        match.group(1).strip()
    )

    return urllib.parse.urljoin(
        BASE_URL,
        raw_url,
    )


# ============================================================
# Movie一覧HTMLパーサー
#
# Movie個別ページへのリンク
#
# /movies/detail/XXX
#
# を起点に、タイトル・日付・サムネイルを取得する。
#
# このパーサーはカテゴリ一覧だけでなく
# /movies/category/ の LATEST MOVIE にも使用する。
# ============================================================

class MovieListParser(
    HTMLParser
):

    def __init__(self):
        super().__init__(
            convert_charrefs=True
        )

        self.movies = []

        self.current_movie = None

        self.movie_link_depth = 0

        self.capture_title = False
        self.capture_date = False

        self.title_parts = []
        self.date_parts = []


    # --------------------------------------------------------
    # class属性をsetに変換
    # --------------------------------------------------------

    @staticmethod
    def get_classes(
        attrs_dict
    ):
        class_value = (
            attrs_dict.get(
                "class",
                "",
            )
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
            href = (
                attrs_dict.get(
                    "href",
                    "",
                )
            )

            match = re.search(
                r'/movies/detail/(\d+)/?',
                href,
                flags=re.IGNORECASE,
            )

            if match:
                movie_id = (
                    match.group(1)
                )

                self.current_movie = {
                    "movie_id":
                        movie_id,
                    "href":
                        href,
                    "title":
                        None,
                    "date":
                        None,
                    "thumbnail":
                        None,
                    "alt_title":
                        None,
                }

                self.movie_link_depth = 1

                self.capture_title = False
                self.capture_date = False

                self.title_parts = []
                self.date_parts = []

                return


        # Movieリンクの外なら以降は不要

        if (
            self.current_movie
            is None
        ):
            return


        # ----------------------------------------------------
        # Movieリンク内部のタグ階層
        # ----------------------------------------------------

        if (
            tag.lower() == "a"
        ):
            self.movie_link_depth += 1


        classes = (
            self.get_classes(
                attrs_dict
            )
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
        # background-image → サムネイル
        # alt → タイトル予備
        # ====================================================

        elif (
            tag.lower() == "img"
        ):
            style_value = (
                attrs_dict.get(
                    "style"
                )
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
                attrs_dict.get(
                    "alt"
                )
            )

            if alt_value:
                self.current_movie[
                    "alt_title"
                ] = alt_value


    # --------------------------------------------------------
    # テキスト
    # --------------------------------------------------------

    def handle_data(
        self,
        data
    ):
        if (
            self.current_movie
            is None
        ):
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

    def handle_endtag(
        self,
        tag
    ):
        if (
            self.current_movie
            is None
        ):
            return


        tag_lower = (
            tag.lower()
        )


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

        if (
            tag_lower == "a"
        ):
            self.movie_link_depth -= 1

            if (
                self.movie_link_depth
                <= 0
            ):
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
# HTMLからMovie候補を取得
# ============================================================

def parse_movie_candidates(
    page_html
):
    parser = MovieListParser()

    parser.feed(
        page_html
    )

    parser.close()

    return parser.movies


# ============================================================
# Movie 1件を正式なJSONデータへ変換
# ============================================================

def build_movie(
    candidate
):
    movie_id = (
        candidate[
            "movie_id"
        ]
    )

    title = clean_text(
        candidate.get(
            "title"
        )
    )

    alt_title = clean_text(
        candidate.get(
            "alt_title"
        )
    )

    raw_date = clean_text(
        candidate.get(
            "date"
        )
    )

    thumbnail = clean_text(
        candidate.get(
            "thumbnail"
        )
    )


    # --------------------------------------------------------
    # タイトル
    #
    # 第一候補：<p class="tit">
    # 第二候補：<img alt="...">
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


    normalized_date = (
        normalize_date(
            raw_date,
            movie_id,
        )
    )


    movie_url = (
        urllib.parse.urljoin(
            BASE_URL,
            candidate["href"],
        )
    )


    return {
        "id":
            f"movie-{movie_id}",
        "type":
            "movie",
        "group":
            "fc",
        "date":
            normalized_date,
        "title":
            title,
        "thumbnail":
            thumbnail,
        "url":
            movie_url,
    }


# ============================================================
# 候補一覧を正式なMovieへ変換
# ============================================================

def build_movies_from_candidates(
    candidates,
    source_name,
    page_number=None,
):
    # --------------------------------------------------------
    # 同一HTML内の重複Movie IDを排除
    # --------------------------------------------------------

    candidates_by_id = {}

    for candidate in candidates:
        movie_id = (
            candidate[
                "movie_id"
            ]
        )

        if (
            movie_id
            not in candidates_by_id
        ):
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

            failure = {
                "source":
                    source_name,
                "movie_id":
                    movie_id,
                "message":
                    str(error),
            }

            if (
                page_number
                is not None
            ):
                failure["page"] = (
                    page_number
                )

            failures.append(
                failure
            )


    return movies, failures


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


    return (
        build_movies_from_candidates(
            candidates,
            category_name,
            page_number,
        )
    )


# ============================================================
# LATEST MOVIEを取得
#
# /movies/category/ に掲載されているMovieを取得する。
#
# ここには各カテゴリにまだ反映されていないMovieが
# 存在する場合がある。
#
# 既存カテゴリと重複するMovieは、
# 最後にMovie IDで統合する。
# ============================================================

def fetch_latest_movies():

    print(
        "LATEST MOVIEを確認..."
    )

    page_html = fetch_html(
        MOVIE_TOP_URL
    )

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


    movies, failures = (
        build_movies_from_candidates(
            candidates,
            "Latest Movie",
        )
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
# 一覧ページ1ページを取得
# ============================================================

def fetch_page(
    category_name,
    list_url,
    page_number,
):
    query = urllib.parse.urlencode(
        {
            "page":
                page_number,
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


    movies, failures = (
        parse_page(
            page_html,
            category_name,
            page_number,
        )
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
# 1カテゴリを最後まで取得
# ============================================================

def fetch_category(
    category_name,
    list_url,
):
    category_movies = []
    category_failures = []

    seen_page_signatures = set()


    for page_number in range(
        1,
        MAX_PAGES + 1,
    ):
        movies, failures = (
            fetch_page(
                category_name,
                list_url,
                page_number,
            )
        )


        category_failures.extend(
            failures
        )


        # ----------------------------------------------------
        # Movieリンク自体がない
        # → 最終ページを超えた
        # ----------------------------------------------------

        if (
            not movies
            and not failures
        ):
            print(
                "  Movieがないため"
                "このカテゴリの取得を終了"
            )

            break


        # ----------------------------------------------------
        # ページ内容の署名
        #
        # サイト側が存在しないページ番号に対して
        # 最終ページなどを返し続ける場合に備える。
        # ----------------------------------------------------

        page_ids = sorted(
            movie["id"]
            for movie in movies
        )

        failure_ids = sorted(
            failure["movie_id"]
            for failure in failures
        )

        signature = (
            tuple(page_ids),
            tuple(failure_ids),
        )


        if (
            signature
            in seen_page_signatures
        ):
            print(
                "  同じページ内容を再検出したため"
                "このカテゴリの取得を終了"
            )

            break


        seen_page_signatures.add(
            signature
        )


        category_movies.extend(
            movies
        )


        time.sleep(
            REQUEST_INTERVAL
        )


    else:
        raise RuntimeError(
            f"{category_name}: "
            f"{MAX_PAGES}ページに達しました。"
            "ページネーションを確認してください。"
        )


    return (
        category_movies,
        category_failures,
    )


# ============================================================
# Movie IDを数値として取得
# ============================================================

def movie_id_number(
    movie
):
    movie_id = str(
        movie.get(
            "id",
            ""
        )
    )

    match = re.search(
        r"(\d+)$",
        movie_id,
    )

    if not match:
        return 0

    return int(
        match.group(1)
    )


# ============================================================
# Movieを統合
#
# LATEST MOVIE と各カテゴリには
# 同じMovieが重複して存在するため、
# id をキーにして1件へ統合する。
#
# LATESTを先に入れ、
# カテゴリ側で同じIDが出ても二重登録しない。
# ============================================================

def merge_movies(
    *movie_groups
):
    movies_by_id = {}


    for movie_group in movie_groups:

        for movie in movie_group:

            movie_id = (
                movie["id"]
            )


            if (
                movie_id
                not in movies_by_id
            ):
                movies_by_id[
                    movie_id
                ] = movie


    return list(
        movies_by_id.values()
    )


# ============================================================
# 保存
# ============================================================

def save_movies(
    movies
):
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


    # ========================================================
    # 1. LATEST MOVIE
    # ========================================================

    latest_movies = []
    all_failures = []


    try:
        (
            latest_movies,
            latest_failures,
        ) = fetch_latest_movies()

        all_failures.extend(
            latest_failures
        )

    except Exception as error:

        # LATEST取得だけの一時的な失敗で
        # 過去カテゴリデータ全体を失わないよう、
        # エラー内容を表示して処理は続行する。
        #
        # ただし最後にfailureとして扱う。

        print(
            "LATEST MOVIE取得エラー："
            f"{error}"
        )

        all_failures.append(
            {
                "source":
                    "Latest Movie",
                "movie_id":
                    None,
                "message":
                    str(error),
            }
        )


    print()


    # ========================================================
    # 2. 各カテゴリ
    # ========================================================

    category_movies = []


    for movie_list in MOVIE_LISTS:

        category_name = (
            movie_list[
                "name"
            ]
        )

        list_url = (
            movie_list[
                "url"
            ]
        )


        print(
            "========================================"
        )

        print(
            f"{category_name} を取得"
        )

        print(
            "========================================"
        )


        movies, failures = (
            fetch_category(
                category_name,
                list_url,
            )
        )


        category_movies.extend(
            movies
        )

        all_failures.extend(
            failures
        )


        print(
            f"{category_name}: "
            f"{len(movies)}件"
        )

        print()


    # ========================================================
    # 3. LATEST + カテゴリを統合
    # ========================================================

    all_movies = merge_movies(
        latest_movies,
        category_movies,
    )


    # ========================================================
    # 4. 日付 → Movie ID の順に並べる
    # ========================================================

    all_movies.sort(
        key=lambda movie: (
            movie.get(
                "date",
                ""
            ),
            movie_id_number(
                movie
            ),
        )
    )


    # ========================================================
    # 5. 診断情報
    # ========================================================

    print(
        "========================================"
    )

    print(
        "取得結果"
    )

    print(
        "========================================"
    )


    print(
        "LATEST MOVIE："
        f"{len(latest_movies)}件"
    )

    print(
        "カテゴリ取得："
        f"{len(category_movies)}件"
    )

    print(
        "重複排除後："
        f"{len(all_movies)}件"
    )

    print(
        "取得失敗："
        f"{len(all_failures)}件"
    )


    # --------------------------------------------------------
    # 最新Movieを表示
    # --------------------------------------------------------

    if all_movies:

        latest_sorted = sorted(
            all_movies,
            key=lambda movie: (
                movie.get(
                    "date",
                    ""
                ),
                movie_id_number(
                    movie
                ),
            ),
            reverse=True,
        )


        print()

        print(
            "最新Movie："
        )


        for movie in latest_sorted[
            :10
        ]:

            print(
                "  "
                f"{movie['date']} "
                f"{movie['id']} "
                f"{movie['title']}"
            )


    # --------------------------------------------------------
    # 失敗があれば保存せず終了
    #
    # 欠落した状態のJSONで既存データを
    # 上書きしないため。
    # --------------------------------------------------------

    if all_failures:

        print()

        print(
            "取得できなかったMovieがあります。"
        )

        print(
            "既存の movie.json は"
            "上書きしません。"
        )


        for failure in all_failures:

            source = (
                failure.get(
                    "source",
                    "Unknown"
                )
            )

            page = (
                failure.get(
                    "page"
                )
            )

            movie_id = (
                failure.get(
                    "movie_id"
                )
            )

            message = (
                failure.get(
                    "message",
                    ""
                )
            )


            location = source

            if (
                page is not None
            ):
                location += (
                    f" / page {page}"
                )


            print(
                "  "
                f"[{location}] "
                f"Movie {movie_id}: "
                f"{message}"
            )


        raise RuntimeError(
            "Movie取得に失敗した項目があるため"
            "処理を終了しました。"
        )


    # ========================================================
    # 6. 保存
    # ========================================================

    save_movies(
        all_movies
    )


    print()

    print(
        f"{OUTPUT_FILE} に"
        f"{len(all_movies)}件保存しました。"
    )

    print(
        "INI Movie取得が完了しました。"
    )


# ============================================================
# 実行
# ============================================================

if __name__ == "__main__":
    main()
