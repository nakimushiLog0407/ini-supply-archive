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

MESSAGE_LIST_URL = (
    f"{BASE_URL}/photo/list/4"
)

OUTPUT_FILE = "data/message.json"
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
    message_id,
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
        f"Message {message_id}: "
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
# Message一覧ページ解析
#
# 診断で確認したHTML構造：
#
# <li id="577">
#   <a href="/photo/331/detail/577">
#     <div class="thumb">
#       ...
#       <figure>
#         <img
#           alt="プロフィール帳 2026"
#           src="/static/common/global-image/blank_thumb.gif"
#           style="background-image:url(...)"
#         >
#       </figure>
#     </div>
#
#     <div class="list__txt">
#       <p class="tit">プロフィール帳 2026</p>
#       <p class="date">2026.05.12</p>
#     </div>
#   </a>
# </li>
#
# 個別ページはFCログインへ遷移するため、
# 一覧ページだけから必要情報を取得する。
#
# Message一覧URL：
# /photo/list/4
#
# 個別URL：
# /photo/331/detail/{id}
# ============================================================

class MessageListParser(
    HTMLParser
):

    def __init__(self):

        super().__init__(
            convert_charrefs=True
        )

        self.messages = []

        self.current_message = None

        self.message_link_depth = 0

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
        # Message個別リンク
        #
        # /photo/331/detail/577
        #
        # category IDは将来変わる可能性を考慮して
        # 数字部分を固定しない。
        # ====================================================

        if (
            tag_lower == "a"
            and self.current_message is None
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

                message_id = (
                    match.group(2)
                )


                self.current_message = {
                    "message_id":
                        message_id,
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


                self.message_link_depth = 1

                self.capture_title = False
                self.capture_date = False

                self.title_parts = []
                self.date_parts = []

                return


        # Messageリンク外なら以降不要

        if (
            self.current_message
            is None
        ):
            return


        # ----------------------------------------------------
        # リンク内部の階層
        # ----------------------------------------------------

        if tag_lower == "a":
            self.message_link_depth += 1


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

                self.current_message[
                    "thumbnail"
                ] = thumbnail


            alt_title = clean_text(
                attrs_dict.get(
                    "alt"
                )
            )


            if alt_title:

                self.current_message[
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
            self.current_message
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
            self.current_message
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

                self.current_message[
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

                self.current_message[
                    "date"
                ] = date_value


            self.capture_date = False
            self.date_parts = []

            return


        # ====================================================
        # Messageリンク終了
        # ====================================================

        if tag_lower == "a":

            self.message_link_depth -= 1


            if (
                self.message_link_depth
                <= 0
            ):

                self.messages.append(
                    self.current_message
                )

                self.current_message = None

                self.message_link_depth = 0

                self.capture_title = False
                self.capture_date = False

                self.title_parts = []
                self.date_parts = []


# ============================================================
# HTMLからMessage候補を取得
# ============================================================

def parse_message_candidates(
    page_html
):

    parser = MessageListParser()

    parser.feed(
        page_html
    )

    parser.close()

    return parser.messages


# ============================================================
# 1件をJSON用データへ変換
# ============================================================

def build_message(
    candidate
):

    message_id = (
        candidate[
            "message_id"
        ]
    )


    title = clean_text(
        candidate.get(
            "title"
        )
    )


    # タイトルが本文から取れなかった場合は
    # imgのaltを使用する

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
            f"Message {message_id}: "
            f"{', '.join(missing)} "
            "を取得できませんでした"
        )


    normalized_date = (
        normalize_date(
            raw_date,
            message_id,
        )
    )


    message_url = (
        urllib.parse.urljoin(
            BASE_URL,
            candidate[
                "href"
            ],
        )
    )


    return {
        "id":
            f"message-{message_id}",
        "type":
            "message",
        "group":
            "fc",
        "date":
            normalized_date,
        "title":
            title,
        "thumbnail":
            thumbnail,
        "url":
            message_url,
    }


# ============================================================
# ページ番号付きURL
# ============================================================

def build_page_url(
    page_number
):

    if page_number == 1:

        return MESSAGE_LIST_URL


    separator = (
        "&"
        if "?" in MESSAGE_LIST_URL
        else "?"
    )


    return (
        f"{MESSAGE_LIST_URL}"
        f"{separator}"
        f"page={page_number}"
    )


# ============================================================
# JSON保存
# ============================================================

def save_json(
    messages
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
            messages,
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
        "INI Message取得を開始します。"
    )

    print(
        f"一覧URL: {MESSAGE_LIST_URL}"
    )

    print()


    messages_by_id = {}

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
            parse_message_candidates(
                page_html
            )
        )


        # 同一ページ内の重複を排除

        candidates_by_id = {}


        for candidate in candidates:

            message_id = (
                candidate.get(
                    "message_id"
                )
            )


            if message_id:

                candidates_by_id[
                    message_id
                ] = candidate


        candidates = list(
            candidates_by_id.values()
        )


        current_page_ids = tuple(
            candidate[
                "message_id"
            ]
            for candidate in candidates
        )


        print(
            "  候補件数: "
            f"{len(candidates)}"
        )


        # ----------------------------------------------------
        # Messageが0件なら最終ページ
        # ----------------------------------------------------

        if not candidates:

            print(
                "  Messageが見つからないため"
                "巡回を終了します。"
            )

            break


        # ----------------------------------------------------
        # 存在しないpage番号で同じページが返された場合の
        # 無限巡回防止
        # ----------------------------------------------------

        if (
            previous_page_ids
            is not None
            and current_page_ids
            == previous_page_ids
        ):

            print(
                "  前ページと同じ内容が"
                "返されたため巡回を終了します。"
            )

            break


        previous_page_ids = (
            current_page_ids
        )


        page_success_count = 0


        for candidate in candidates:

            message_id = (
                candidate[
                    "message_id"
                ]
            )


            try:

                message = build_message(
                    candidate
                )


                messages_by_id[
                    message[
                        "id"
                    ]
                ] = message


                page_success_count += 1


            except Exception as error:

                failures.append(
                    {
                        "page":
                            page_number,
                        "message_id":
                            message_id,
                        "error":
                            str(error),
                    }
                )


                print(
                    "  [ERROR] "
                    f"Message {message_id}: "
                    f"{error}"
                )


        print(
            "  取得成功: "
            f"{page_success_count}"
        )

        print()


        time.sleep(
            REQUEST_INTERVAL
        )


    else:

        raise RuntimeError(
            "MAX_PAGES に到達しました。"
            "ページネーション構造を確認してください。"
        )


    # ========================================================
    # 取得結果チェック
    # ========================================================

    if failures:

        print()
        print(
            "取得に失敗したMessageがあります。"
        )


        for failure in failures:

            print(
                "  "
                f"Page {failure['page']} / "
                f"Message {failure['message_id']}: "
                f"{failure['error']}"
            )


        raise RuntimeError(
            "一部のMessageを正常に取得できなかったため、"
            "JSONは更新しません。"
        )


    if not messages_by_id:

        raise RuntimeError(
            "Messageを1件も取得できませんでした。"
        )


    # ========================================================
    # 新しい順に並べる
    #
    # 同日の場合はIDの大きいものを先にする。
    # ========================================================

    messages = list(
        messages_by_id.values()
    )


    messages.sort(
        key=lambda item: (
            item[
                "date"
            ],
            int(
                item[
                    "id"
                ].split(
                    "-"
                )[-1]
            ),
        ),
        reverse=True,
    )


    # ========================================================
    # JSON保存
    # ========================================================

    save_json(
        messages
    )


    print()
    print(
        "========================================"
    )

    print(
        "INI Message取得完了"
    )

    print(
        f"取得件数: {len(messages)}"
    )

    print(
        f"保存先: {OUTPUT_FILE}"
    )

    print(
        "========================================"
    )


if __name__ == "__main__":
    main()
