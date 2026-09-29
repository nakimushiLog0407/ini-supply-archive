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

RADIO_LIST_URL = (
    f"{BASE_URL}/streams/list/6/0/"
)

OUTPUT_FILE = "data/radio.json"
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
    radio_id,
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
        f"Radio {radio_id}: "
        f"日付形式を解析できません: "
        f"{raw_date}"
    )


# ============================================================
# サムネイルURL取得
#
# 診断結果より、通常の src は blank_thumb.gif。
# 実画像は style の background-image に入っている。
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
# Radio一覧HTMLパーサー
#
# 診断で確認した実構造：
#
# /streams/detail/623
# <p class="tit">タイトル</p>
# <p class="date">2026.09.29</p>
# <img style="background-image: url(...)">
#
# を使用する。
# ============================================================

class RadioListParser(
    HTMLParser
):

    def __init__(self):
        super().__init__(
            convert_charrefs=True
        )

        self.radios = []

        self.current_radio = None
        self.radio_link_depth = 0

        self.capture_title = False
        self.capture_date = False

        self.title_parts = []
        self.date_parts = []


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
        # Radio個別ページへのリンクを検出
        # ====================================================

        if (
            tag.lower() == "a"
            and self.current_radio is None
        ):
            href = (
                attrs_dict.get(
                    "href",
                    "",
                )
            )

            match = re.search(
                r'/streams/detail/(\d+)/?',
                href,
                flags=re.IGNORECASE,
            )

            if match:
                radio_id = (
                    match.group(1)
                )

                self.current_radio = {
                    "radio_id":
                        radio_id,
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

                self.radio_link_depth = 1

                self.capture_title = False
                self.capture_date = False

                self.title_parts = []
                self.date_parts = []

                return


        if (
            self.current_radio
            is None
        ):
            return


        if (
            tag.lower() == "a"
        ):
            self.radio_link_depth += 1


        classes = (
            self.get_classes(
                attrs_dict
            )
        )


        # ====================================================
        # タイトル
        # ====================================================

        if (
            tag.lower() == "p"
            and "tit" in classes
        ):
            self.capture_title = True
            self.title_parts = []


        # ====================================================
        # 公開日
        # ====================================================

        elif (
            tag.lower() == "p"
            and "date" in classes
        ):
            self.capture_date = True
            self.date_parts = []


        # ====================================================
        # サムネイル
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
                self.current_radio[
                    "thumbnail"
                ] = thumbnail


            alt_value = clean_text(
                attrs_dict.get(
                    "alt"
                )
            )

            if alt_value:
                self.current_radio[
                    "alt_title"
                ] = alt_value


    # --------------------------------------------------------
    # テキスト
    # --------------------------------------------------------

    def handle_data(
        self,
        data,
    ):
        if (
            self.current_radio
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
            self.current_radio
            is None
        ):
            return


        tag_lower = (
            tag.lower()
        )


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
                self.current_radio[
                    "title"
                ] = title

            self.capture_title = False
            self.title_parts = []

            return


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
                self.current_radio[
                    "date"
                ] = date_value

            self.capture_date = False
            self.date_parts = []

            return


        if (
            tag_lower == "a"
        ):
            self.radio_link_depth -= 1

            if (
                self.radio_link_depth
                <= 0
            ):
                self.radios.append(
                    self.current_radio
                )

                self.current_radio = None
                self.radio_link_depth = 0

                self.capture_title = False
                self.capture_date = False

                self.title_parts = []
                self.date_parts = []


# ============================================================
# HTMLからRadio候補を取得
# ============================================================

def parse_radio_candidates(
    page_html
):
    parser = RadioListParser()

    parser.feed(
        page_html
    )

    parser.close()

    return parser.radios


# ============================================================
# Radio 1件をJSON形式へ変換
# ============================================================

def build_radio(
    candidate
):
    radio_id = (
        candidate[
            "radio_id"
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


    # タイトル取得の予備としてimg altも使用
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
            f"Radio {radio_id}: "
            f"{', '.join(missing)} "
            "を取得できませんでした"
        )


    normalized_date = (
        normalize_date(
            raw_date,
            radio_id,
        )
    )


    radio_url = (
        urllib.parse.urljoin(
            BASE_URL,
            candidate["href"],
        )
    )


    return {
        "id":
            f"radio-{radio_id}",
        "type":
            "radio",
        "group":
            "fc",
        "date":
            normalized_date,
        "title":
            title,
        "thumbnail":
            thumbnail,
        "url":
            radio_url,
    }


# ============================================================
# 1ページ分を変換
# ============================================================

def build_radios_from_candidates(
    candidates,
    page_number,
):
    candidates_by_id = {}

    for candidate in candidates:
        radio_id = (
            candidate[
                "radio_id"
            ]
        )

        if (
            radio_id
            not in candidates_by_id
        ):
            candidates_by_id[
                radio_id
            ] = candidate


    radios = []
    failures = []


    for (
        radio_id,
        candidate,
    ) in candidates_by_id.items():

        try:
            radio = build_radio(
                candidate
            )

            radios.append(
                radio
            )

        except ValueError as error:
            failures.append(
                {
                    "page":
                        page_number,
                    "radio_id":
                        radio_id,
                    "message":
                        str(error),
                }
            )


    return radios, failures


# ============================================================
# 指定ページを取得
# ============================================================

def fetch_page(
    page_number
):
    query = urllib.parse.urlencode(
        {
            "page":
                page_number,
        }
    )

    url = (
        f"{RADIO_LIST_URL}?{query}"
    )


    print(
        f"Radio "
        f"{page_number}ページ目を確認..."
    )


    page_html = fetch_html(
        url
    )


    candidates = (
        parse_radio_candidates(
            page_html
        )
    )


    print(
        "  検出："
        f"Radioリンク "
        f"{len(candidates)}件"
    )


    if not candidates:
        return [], []


    radios, failures = (
        build_radios_from_candidates(
            candidates,
            page_number,
        )
    )


    print(
        f"  {len(radios)}件取得"
    )


    if failures:
        for failure in failures:
            print(
                "  警告："
                f"{failure['message']}"
            )


    return radios, failures


# ============================================================
# 全ページ取得
# ============================================================

def fetch_all_radios():
    all_radios = []
    all_failures = []

    seen_page_signatures = set()


    for page_number in range(
        1,
        MAX_PAGES + 1,
    ):
        radios, failures = (
            fetch_page(
                page_number
            )
        )


        all_failures.extend(
            failures
        )


        # ----------------------------------------------------
        # Radioがなくなったら終了
        # ----------------------------------------------------

        if (
            not radios
            and not failures
        ):
            print(
                "  Radioがないため"
                "取得を終了します。"
            )

            break


        # ----------------------------------------------------
        # 同じページが返され続ける場合の安全対策
        # ----------------------------------------------------

        radio_ids = sorted(
            radio["id"]
            for radio in radios
        )

        failure_ids = sorted(
            failure["radio_id"]
            for failure in failures
        )

        signature = (
            tuple(radio_ids),
            tuple(failure_ids),
        )


        if (
            signature
            in seen_page_signatures
        ):
            print(
                "  同じページ内容を再検出したため"
                "取得を終了します。"
            )

            break


        seen_page_signatures.add(
            signature
        )


        all_radios.extend(
            radios
        )


        time.sleep(
            REQUEST_INTERVAL
        )


    else:
        raise RuntimeError(
            f"{MAX_PAGES}ページに達しました。"
            "ページネーションを確認してください。"
        )


    return (
        all_radios,
        all_failures,
    )


# ============================================================
# Radio IDを数値として取得
# ============================================================

def radio_id_number(
    radio
):
    radio_id = str(
        radio.get(
            "id",
            ""
        )
    )

    match = re.search(
        r"(\d+)$",
        radio_id,
    )

    if not match:
        return 0

    return int(
        match.group(1)
    )


# ============================================================
# ID重複排除
# ============================================================

def deduplicate_radios(
    radios
):
    radios_by_id = {}

    for radio in radios:
        radio_id = (
            radio["id"]
        )

        if (
            radio_id
            not in radios_by_id
        ):
            radios_by_id[
                radio_id
            ] = radio


    return list(
        radios_by_id.values()
    )


# ============================================================
# JSON保存
#
# 一時ファイルに正常に書き終えてから置換する。
# ============================================================

def save_radios(
    radios
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
            radios,
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
        "INI Radio取得を開始します。"
    )

    print(
        "取得元：",
        RADIO_LIST_URL,
    )

    print()


    radios, failures = (
        fetch_all_radios()
    )


    # ========================================================
    # 重複排除
    # ========================================================

    radios = (
        deduplicate_radios(
            radios
        )
    )


    # ========================================================
    # 日付 → Radio ID の順に並べる
    # ========================================================

    radios.sort(
        key=lambda radio: (
            radio.get(
                "date",
                ""
            ),
            radio_id_number(
                radio
            ),
        )
    )


    # ========================================================
    # 診断情報
    # ========================================================

    print()
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
        "Radio："
        f"{len(radios)}件"
    )

    print(
        "取得失敗："
        f"{len(failures)}件"
    )


    # ========================================================
    # 最新10件をログ表示
    # ========================================================

    if radios:

        latest_sorted = sorted(
            radios,
            key=lambda radio: (
                radio.get(
                    "date",
                    ""
                ),
                radio_id_number(
                    radio
                ),
            ),
            reverse=True,
        )


        print()
        print(
            "最新Radio："
        )


        for radio in latest_sorted[
            :10
        ]:

            print(
                "  "
                f"{radio['date']} "
                f"{radio['id']} "
                f"{radio['title']}"
            )


    # ========================================================
    # 1件でも取得失敗があれば保存しない
    #
    # 不完全なradio.jsonで既存データを
    # 上書きしないため。
    # ========================================================

    if failures:

        print()
        print(
            "取得できなかったRadioがあります。"
        )

        print(
            "既存の radio.json は"
            "上書きしません。"
        )


        for failure in failures:

            print(
                "  "
                f"[page {failure['page']}] "
                f"Radio {failure['radio_id']}: "
                f"{failure['message']}"
            )


        raise RuntimeError(
            "Radio取得に失敗した項目があるため"
            "処理を終了しました。"
        )


    # ========================================================
    # 保存
    # ========================================================

    save_radios(
        radios
    )


    print()
    print(
        f"{OUTPUT_FILE} に"
        f"{len(radios)}件保存しました。"
    )

    print(
        "INI Radio取得が完了しました。"
    )


if __name__ == "__main__":
    main()
