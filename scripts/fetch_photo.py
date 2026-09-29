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

PHOTO_LIST_URL = (
    f"{BASE_URL}/photo/list/3"
)

OUTPUT_FILE = "data/photo.json"
TEMP_FILE = OUTPUT_FILE + ".tmp"

REQUEST_INTERVAL = 0.5

# ページネーション異常時の無限巡回防止
MAX_PAGES = 100


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

    value = html.unescape(
        value
    )

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
    photo_id,
):

    raw_date = (
        raw_date.strip()
    )

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
        f"Photo {photo_id}: "
        "日付形式を解析できません: "
        f"{raw_date}"
    )


# ============================================================
# background-image から画像URLを取得
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
        match.group(1)
        .strip()
    )


    return urllib.parse.urljoin(
        BASE_URL,
        raw_url,
    )


# ============================================================
# Photo一覧ページ解析
#
# 確認済みHTML構造：
#
# <li id="619">
#   <a href="/photo/331/detail/619">
#     ...
#     <img
#       src="/static/common/global-image/blank_thumb.gif"
#       style="background-image:url(...)"
#     >
#     ...
#     <p class="tit">タイトル</p>
#     <p class="date">2026.09.26</p>
#   </a>
# </li>
#
# 個別ページはFCログインへ遷移するため、
# 一覧ページだけから必要情報を取得する。
# ============================================================

class PhotoListParser(
    HTMLParser
):

    def __init__(self):

        super().__init__(
            convert_charrefs=True
        )

        self.photos = []

        self.current_photo = None

        self.photo_link_depth = 0

        self.capture_title = False
        self.capture_date = False

        self.title_parts = []
        self.date_parts = []


    # --------------------------------------------------------
    # class属性
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

        attrs_dict = dict(
            attrs
        )

        tag_lower = (
            tag.lower()
        )


        # ====================================================
        # Photo個別リンク
        #
        # /photo/331/detail/619
        #
        # category IDは将来変わる可能性を考慮して
        # 数字部分を固定しない。
        # ====================================================

        if (
            tag_lower == "a"
            and self.current_photo is None
        ):

            href = (
                attrs_dict.get(
                    "href",
                    "",
                )
            )


            match = re.search(
                r"/photo/"
                r"(\d+)"
                r"/detail/"
                r"(\d+)"
                r"/?",
                href,
                flags=re.IGNORECASE,
            )


            if match:

                category_id = (
                    match.group(1)
                )

                photo_id = (
                    match.group(2)
                )


                self.current_photo = {
                    "photo_id":
                        photo_id,
                    "category_id":
                        category_id,
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


                self.photo_link_depth = 1

                self.capture_title = False
                self.capture_date = False

                self.title_parts = []
                self.date_parts = []

                return


        # Photoリンク外なら以降不要

        if (
            self.current_photo
            is None
        ):
            return


        # ----------------------------------------------------
        # リンク内部の階層
        # ----------------------------------------------------

        if tag_lower == "a":
            self.photo_link_depth += 1


        classes = (
            self.get_classes(
                attrs_dict
            )
        )


        # ====================================================
        # タイトル
        # ====================================================

        if (
            tag_lower == "p"
            and "tit" in classes
        ):

            self.capture_title = True
            self.title_parts = []


        # ====================================================
        # 公開日
        # ====================================================

        elif (
            tag_lower == "p"
            and "date" in classes
        ):

            self.capture_date = True
            self.date_parts = []


        # ====================================================
        # サムネイル
        #
        # srcはblank_thumb.gifなので、
        # style内のbackground-imageを使用。
        # ====================================================

        elif tag_lower == "img":

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

                self.current_photo[
                    "thumbnail"
                ] = thumbnail


            alt_title = clean_text(
                attrs_dict.get(
                    "alt"
                )
            )


            if alt_title:

                self.current_photo[
                    "alt_title"
                ] = alt_title


    # --------------------------------------------------------
    # テキスト
    # --------------------------------------------------------

    def handle_data(
        self,
        data,
    ):

        if (
            self.current_photo
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
        tag,
    ):

        if (
            self.current_photo
            is None
        ):
            return


        tag_lower = (
            tag.lower()
        )


        # ====================================================
        # タイトル終了
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

                self.current_photo[
                    "title"
                ] = title


            self.capture_title = False
            self.title_parts = []

            return


        # ====================================================
        # 日付終了
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

                self.current_photo[
                    "date"
                ] = date_value


            self.capture_date = False
            self.date_parts = []

            return


        # ====================================================
        # Photoリンク終了
        # ====================================================

        if tag_lower == "a":

            self.photo_link_depth -= 1


            if (
                self.photo_link_depth
                <= 0
            ):

                self.photos.append(
                    self.current_photo
                )

                self.current_photo = None

                self.photo_link_depth = 0

                self.capture_title = False
                self.capture_date = False

                self.title_parts = []
                self.date_parts = []


# ============================================================
# HTMLからPhoto候補を取得
# ============================================================

def parse_photo_candidates(
    page_html
):

    parser = PhotoListParser()

    parser.feed(
        page_html
    )

    parser.close()

    return parser.photos


# ============================================================
# 1件をJSON用データへ変換
# ============================================================

def build_photo(
    candidate
):

    photo_id = (
        candidate[
            "photo_id"
        ]
    )


    title = clean_text(
        candidate.get(
            "title"
        )
    )


    if not title:

        title = clean_text(
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
            f"Photo {photo_id}: "
            f"{', '.join(missing)} "
            "を取得できませんでした"
        )


    normalized_date = (
        normalize_date(
            raw_date,
            photo_id,
        )
    )


    photo_url = (
        urllib.parse.urljoin(
            BASE_URL,
            candidate[
                "href"
            ],
        )
    )


    return {
        "id":
            f"photo-{photo_id}",
        "type":
            "photo",
        "group":
            "fc",
        "date":
            normalized_date,
        "title":
            title,
        "thumbnail":
            thumbnail,
        "url":
            photo_url,
    }


# ============================================================
# ページ番号付きURL
# ============================================================

def build_page_url(
    page_number
):

    if page_number == 1:

        return PHOTO_LIST_URL


    separator = (
        "&"
        if "?" in PHOTO_LIST_URL
        else "?"
    )


    return (
        f"{PHOTO_LIST_URL}"
        f"{separator}"
        f"page={page_number}"
    )


# ============================================================
# JSON保存
# ============================================================

def save_json(
    photos
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
            photos,
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
# メイン
# ============================================================

def main():

    print(
        "INI Photo取得を開始します。"
    )

    print(
        f"一覧URL: {PHOTO_LIST_URL}"
    )

    print()


    photos_by_id = {}

    failures = []

    previous_page_ids = None


    # ========================================================
    # ページを古いところまで順番に巡回
    # ========================================================

    for page_number in range(
        1,
        MAX_PAGES + 1,
    ):

        page_url = (
            build_page_url(
                page_number
            )
        )


        print(
            f"[Page {page_number}] "
            f"{page_url}"
        )


        try:

            page_html = fetch_html(
                page_url
            )

        except Exception as error:

            raise RuntimeError(
                f"Page {page_number}: "
                "HTML取得に失敗しました: "
                f"{error}"
            ) from error


        candidates = (
            parse_photo_candidates(
                page_html
            )
        )


        # 同一ページ内の重複を排除

        candidates_by_id = {}


        for candidate in candidates:

            photo_id = (
                candidate[
                    "photo_id"
                ]
            )


            if (
                photo_id
                not in candidates_by_id
            ):

                candidates_by_id[
                    photo_id
                ] = candidate


        print(
            "  検出: "
            f"{len(candidates_by_id)}件"
        )


        # ====================================================
        # 0件になったら最終ページを超えたと判断
        # ====================================================

        if not candidates_by_id:

            print(
                "  Photoが0件のため"
                "巡回を終了します。"
            )

            break


        current_page_ids = tuple(
            candidates_by_id.keys()
        )


        # ====================================================
        # ページ番号を無視して同じページを返すサイト対策
        # ====================================================

        if (
            previous_page_ids
            == current_page_ids
        ):

            print(
                "  前ページと同じPhoto一覧が"
                "返されたため巡回を終了します。"
            )

            break


        previous_page_ids = (
            current_page_ids
        )


        page_success_count = 0
        page_failure_count = 0


        # ====================================================
        # JSONデータへ変換
        # ====================================================

        for (
            photo_id,
            candidate,
        ) in candidates_by_id.items():

            try:

                photo = build_photo(
                    candidate
                )


                photos_by_id[
                    photo["id"]
                ] = photo


                page_success_count += 1


            except ValueError as error:

                page_failure_count += 1


                failures.append(
                    {
                        "page":
                            page_number,
                        "photo_id":
                            photo_id,
                        "message":
                            str(error),
                    }
                )


        print(
            "  成功: "
            f"{page_success_count}件"
        )

        print(
            "  失敗: "
            f"{page_failure_count}件"
        )


        time.sleep(
            REQUEST_INTERVAL
        )


    else:

        raise RuntimeError(
            f"最大ページ数 {MAX_PAGES} "
            "まで到達しました。"
            "ページネーション構造を"
            "確認してください。"
        )


    # ========================================================
    # 取得失敗が1件でもあればJSONを書き換えない
    # ========================================================

    if failures:

        print()
        print(
            "========================================"
        )

        print(
            "取得失敗"
        )

        print(
            "========================================"
        )


        for failure in failures:

            print(
                f"Page {failure['page']} / "
                f"Photo {failure['photo_id']}: "
                f"{failure['message']}"
            )


        raise RuntimeError(
            f"{len(failures)}件のPhotoで"
            "必要情報を取得できなかったため、"
            "photo.jsonは更新しません。"
        )


    # ========================================================
    # 日付 → ID の順で並べる
    # ========================================================

    photos = list(
        photos_by_id.values()
    )


    photos.sort(
        key=lambda item: (
            item["date"],
            int(
                item["id"]
                .replace(
                    "photo-",
                    ""
                )
            ),
        )
    )


    # ========================================================
    # 最低限の安全確認
    # ========================================================

    if not photos:

        raise RuntimeError(
            "Photoを1件も取得できませんでした。"
        )


    # ========================================================
    # 保存
    # ========================================================

    save_json(
        photos
    )


    # ========================================================
    # 結果表示
    # ========================================================

    print()
    print(
        "========================================"
    )

    print(
        "Photo取得完了"
    )

    print(
        "========================================"
    )


    print(
        f"合計: {len(photos)}件"
    )


    print(
        "最古: "
        f"{photos[0]['date']} / "
        f"{photos[0]['id']} / "
        f"{photos[0]['title']}"
    )


    print(
        "最新: "
        f"{photos[-1]['date']} / "
        f"{photos[-1]['id']} / "
        f"{photos[-1]['title']}"
    )


    print(
        f"保存先: {OUTPUT_FILE}"
    )


if __name__ == "__main__":

    main()
