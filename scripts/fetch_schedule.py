import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


# ==========================================================
# 設定
# ==========================================================

BASE_URL = "https://ini-official.com"

SCHEDULE_LIST_URL = (
    BASE_URL
    + "/schedule/list/{year}/{month}/"
    + "?cat=L_ALL,live02,live03,live04,"
    + "live05,live06,live07,live08,live09"
)

OUTPUT_PATH = Path("data/schedule.json")

# ----------------------------------------------------------
# 差分取得設定
#
# 通常実行では過去全件を取り直さず、
# 現在月から何か月前まで再確認するか。
#
# 公式サイト側で直近Scheduleが後から修正された場合にも
# 対応できるよう、2か月前から再取得する。
# ----------------------------------------------------------

REFRESH_PAST_MONTHS = 2

# 将来発表済みの仕事も取得するため、
# 現在月から12か月先まで確認する。
FUTURE_MONTHS = 12

REQUEST_INTERVAL = 0.25
TIMEOUT = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/18.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept": (
        "text/html,"
        "application/xhtml+xml,"
        "application/xml;q=0.9,"
        "*/*;q=0.8"
    ),
    "Accept-Language": (
        "ja-JP,ja;q=0.9,"
        "en-US;q=0.8,en;q=0.7"
    ),
}


# ==========================================================
# メンバー名
#
# JSONには左側の統一名称を保存する。
# 右側は公式サイト上で検出する表記ゆれ。
# ==========================================================

MEMBER_ALIASES = {
    "池﨑理人": [
        "池﨑理人",
        "池﨑 理人",
    ],
    "尾崎匠海": [
        "尾崎匠海",
        "尾崎 匠海",
    ],
    "木村柾哉": [
        "木村柾哉",
        "木村 柾哉",
    ],
    "後藤威尊": [
        "後藤威尊",
        "後藤 威尊",
    ],
    "佐野雄大": [
        "佐野雄大",
        "佐野 雄大",
    ],
    "シュウ・フェンファン": [
        "シュウ・フェンファン",
        "シュウ フェンファン",
        "許豊凡",
        "許 豊凡",
    ],
    "髙塚大夢": [
        "髙塚大夢",
        "髙塚 大夢",
    ],
    "田島将吾": [
        "田島将吾",
        "田島 将吾",
    ],
    "西洸人": [
        "西洸人",
        "西 洸人",
    ],
    "藤牧京介": [
        "藤牧京介",
        "藤牧 京介",
    ],
    "松田迅": [
        "松田迅",
        "松田 迅",
    ],
}


# ==========================================================
# Scheduleカテゴリ
# ==========================================================

CATEGORY_MAP = {
    "Release": "release",
    "Live／Event": "live_event",
    "Live/Event": "live_event",
    "Live / Event": "live_event",
    "Live・Event": "live_event",
    "TV": "tv",
    "Radio": "radio",
    "Magazine": "magazine",
    "Web Media": "web_media",
    "Birthday": "birthday",
    "Other": "other",
}


# ==========================================================
# HTTP
# ==========================================================

session = requests.Session()
session.headers.update(HEADERS)


def fetch_html(url):
    response = session.get(
        url,
        timeout=TIMEOUT,
        allow_redirects=True,
    )

    response.raise_for_status()

    return response.text, response.url


# ==========================================================
# 共通
# ==========================================================

def clean_text(value):
    if not value:
        return ""

    value = value.replace(
        "\u3000",
        " ",
    )

    value = value.replace(
        "\xa0",
        " ",
    )

    return re.sub(
        r"[ \t\r\f\v]+",
        " ",
        value,
    ).strip()


def clean_multiline_text(value):
    if not value:
        return ""

    value = value.replace(
        "\r\n",
        "\n",
    ).replace(
        "\r",
        "\n",
    )

    value = value.replace(
        "\u3000",
        " ",
    ).replace(
        "\xa0",
        " ",
    )

    lines = []

    for raw_line in value.split("\n"):
        line = re.sub(
            r"[ \t]+",
            " ",
            raw_line,
        ).strip()

        if line:
            lines.append(line)

    return "\n".join(lines)


# ==========================================================
# Schedule本文末尾のUI文字列を除外
# ==========================================================

def clean_schedule_detail_text(value):
    text = clean_multiline_text(
        value
    )

    if not text:
        return ""

    lines = text.split(
        "\n"
    )

    while (
        lines
        and not lines[-1].strip()
    ):
        lines.pop()

    if (
        lines
        and lines[-1].strip().lower()
        == "back"
    ):
        lines.pop()

    if (
        lines
        and lines[-1].strip().lower()
        == "share"
    ):
        lines.pop()

    return "\n".join(
        lines
    ).strip()


def absolute_url(base_url, value):
    if not value:
        return ""

    return urljoin(
        base_url,
        value,
    )


def normalize_url(url):
    if not url:
        return ""

    return url.split(
        "#",
        1,
    )[0]


# ==========================================================
# 月計算
# ==========================================================

def add_months(year, month, amount):
    total = (
        year * 12
        + (month - 1)
        + amount
    )

    new_year = total // 12
    new_month = total % 12 + 1

    return new_year, new_month


def iter_months(
    start_year,
    start_month,
    end_year,
    end_month,
):
    year = start_year
    month = start_month

    while (
        year < end_year
        or (
            year == end_year
            and month <= end_month
        )
    ):
        yield year, month

        month += 1

        if month > 12:
            month = 1
            year += 1


def month_key(year, month):
    return (
        f"{year:04d}-"
        f"{month:02d}"
    )


# ==========================================================
# 日付
# ==========================================================

def make_date(
    year,
    month,
    day,
):
    try:
        return (
            f"{year:04d}-"
            f"{month:02d}-"
            f"{int(day):02d}"
        )

    except Exception:
        return ""


def extract_date_from_text(
    text,
    default_year=None,
    default_month=None,
):
    if not text:
        return ""

    match = re.search(
        r"(20\d{2})"
        r"[./-]"
        r"(\d{1,2})"
        r"[./-]"
        r"(\d{1,2})",
        text,
    )

    if match:
        return make_date(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
        )

    if (
        default_year is not None
        and default_month is not None
    ):
        match = re.search(
            r"\b"
            + re.escape(
                f"{default_month:02d}"
            )
            + r"\s+"
            + r"(\d{1,2})"
            + r"\b",
            text,
        )

        if match:
            return make_date(
                default_year,
                default_month,
                int(match.group(1)),
            )

        match = re.search(
            r"(\d{1,2})日",
            text,
        )

        if match:
            return make_date(
                default_year,
                default_month,
                int(match.group(1)),
            )

    return ""


# ==========================================================
# カテゴリ
# ==========================================================

def normalize_category(
    category_label,
):
    label = clean_text(
        category_label
    )

    if label in CATEGORY_MAP:
        return (
            CATEGORY_MAP[label],
            label,
        )

    lower = label.lower()

    if "release" in lower:
        return "release", "Release"

    if (
        "live" in lower
        or "event" in lower
    ):
        return (
            "live_event",
            "Live／Event",
        )

    if label == "TV":
        return "tv", "TV"

    if "radio" in lower:
        return "radio", "Radio"

    if "magazine" in lower:
        return (
            "magazine",
            "Magazine",
        )

    if (
        "web" in lower
        and "media" in lower
    ):
        return (
            "web_media",
            "Web Media",
        )

    if "birthday" in lower:
        return (
            "birthday",
            "Birthday",
        )

    if "other" in lower:
        return (
            "other",
            "Other",
        )

    return (
        "other",
        label or "Other",
    )


# ==========================================================
# メンバー抽出
# ==========================================================

def normalize_for_member_search(text):
    if not text:
        return ""

    text = text.replace(
        "\u3000",
        "",
    )

    text = re.sub(
        r"\s+",
        "",
        text,
    )

    return text


def extract_members(text):
    normalized_text = (
        normalize_for_member_search(
            text
        )
    )

    members = []

    for official_name, aliases in (
        MEMBER_ALIASES.items()
    ):
        found = False

        for alias in aliases:
            normalized_alias = (
                normalize_for_member_search(
                    alias
                )
            )

            if (
                normalized_alias
                and normalized_alias
                in normalized_text
            ):
                found = True
                break

        if found:
            members.append(
                official_name
            )

    return members


# ==========================================================
# 詳細ページURL
# ==========================================================

def extract_schedule_id(url):
    if not url:
        return ""

    match = re.search(
        r"/schedule/detail/(\d+)",
        url,
    )

    if not match:
        return ""

    return match.group(1)


# ==========================================================
# 一覧ページ解析
# ==========================================================

def find_schedule_entries(
    soup,
    page_url,
    year,
    month,
):
    entries = []

    seen_ids = set()

    detail_links = []

    for link in soup.find_all(
        "a",
        href=True,
    ):
        full_url = absolute_url(
            page_url,
            link.get(
                "href",
                "",
            ),
        )

        schedule_id = (
            extract_schedule_id(
                full_url
            )
        )

        if not schedule_id:
            continue

        detail_links.append(
            (
                link,
                full_url,
                schedule_id,
            )
        )

    for (
        link,
        detail_url,
        schedule_id,
    ) in detail_links:

        if schedule_id in seen_ids:
            continue

        container = link

        for _ in range(8):
            if container is None:
                break

            if (
                container.name
                in {
                    "li",
                    "article",
                    "tr",
                }
            ):
                break

            container = (
                container.parent
            )

        if container is None:
            container = link

        container_text = clean_text(
            container.get_text(
                " ",
                strip=True,
            )
        )

        date = ""

        date_element = (
            container.select_one(
                ".date"
            )
        )

        if date_element:
            date = (
                extract_date_from_text(
                    clean_text(
                        date_element.get_text(
                            " ",
                            strip=True,
                        )
                    ),
                    year,
                    month,
                )
            )

        if not date:
            date = (
                extract_date_from_text(
                    container_text,
                    year,
                    month,
                )
            )

        category_label = ""

        category_element = (
            container.select_one(
                ".category"
            )
        )

        if category_element:
            category_label = (
                clean_text(
                    category_element.get_text(
                        " ",
                        strip=True,
                    )
                )
            )

        if not category_label:
            for label in CATEGORY_MAP:
                if (
                    label
                    in container_text
                ):
                    category_label = (
                        label
                    )
                    break

        category, category_label = (
            normalize_category(
                category_label
            )
        )

        title = ""

        title_element = (
            container.select_one(
                ".title"
            )
        )

        if title_element:
            title = clean_text(
                title_element.get_text(
                    " ",
                    strip=True,
                )
            )

        if not title:
            title = clean_text(
                link.get_text(
                    " ",
                    strip=True,
                )
            )

        if not title:
            title = container_text

        if not date:
            print(
                "  WARNING:",
                schedule_id,
                "の日付を一覧から取得できませんでした。"
            )

        if not title:
            print(
                "  WARNING:",
                schedule_id,
                "のタイトルを一覧から取得できませんでした。"
            )

        entries.append(
            {
                "id": (
                    f"schedule-{schedule_id}"
                ),
                "scheduleId": (
                    schedule_id
                ),
                "type": "schedule",
                "group": "schedule",
                "category": category,
                "categoryLabel": (
                    category_label
                ),
                "date": date,
                "title": title,
                "url": normalize_url(
                    detail_url
                ),
            }
        )

        seen_ids.add(
            schedule_id
        )

    return entries


# ==========================================================
# 詳細ページ本文の候補を取得
# ==========================================================

def find_detail_content(soup):
    selectors = [
        ".schedule_detail",
        ".schedule-detail",
        ".detail",
        ".detail_body",
        ".detail-body",
        ".article_body",
        ".article-body",
        ".content",
        "article",
        "main",
    ]

    candidates = []

    for selector in selectors:
        for element in soup.select(
            selector
        ):
            text = (
                clean_multiline_text(
                    element.get_text(
                        "\n",
                        strip=True,
                    )
                )
            )

            if not text:
                continue

            candidates.append(
                (
                    len(text),
                    element,
                    text,
                )
            )

    if candidates:
        candidates.sort(
            key=lambda item: item[0]
        )

        meaningful = [
            item
            for item in candidates
            if item[0] >= 30
        ]

        if meaningful:
            return meaningful[0][1], meaningful[0][2]

        return (
            candidates[-1][1],
            candidates[-1][2],
        )

    body = soup.body

    if body:
        return (
            body,
            clean_multiline_text(
                body.get_text(
                    "\n",
                    strip=True,
                )
            ),
        )

    return (
        soup,
        clean_multiline_text(
            soup.get_text(
                "\n",
                strip=True,
            )
        ),
    )


# ==========================================================
# 詳細ページのヘッダー情報
# ==========================================================

def extract_detail_header(
    soup,
    fallback,
):
    page_text = clean_text(
        soup.get_text(
            " ",
            strip=True,
        )
    )

    date = (
        extract_date_from_text(
            page_text
        )
        or fallback.get(
            "date",
            "",
        )
    )

    category_label = ""

    for selector in [
        ".category",
        ".cat",
        "[class*='category']",
    ]:
        element = (
            soup.select_one(
                selector
            )
        )

        if not element:
            continue

        text = clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if text:
            category_label = text
            break

    if not category_label:
        category_label = (
            fallback.get(
                "categoryLabel",
                "",
            )
        )

    category, category_label = (
        normalize_category(
            category_label
        )
    )

    title = ""

    for selector in [
        "h1",
        ".title",
        ".tit",
        "[class*='title']",
    ]:
        element = (
            soup.select_one(
                selector
            )
        )

        if not element:
            continue

        text = clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if (
            text
            and text.lower()
            != "schedule"
        ):
            title = text
            break

    if not title:
        title = fallback.get(
            "title",
            "",
        )

    return (
        date,
        category,
        category_label,
        title,
    )


# ==========================================================
# SNS共有リンク判定
# ==========================================================

def is_social_share_url(url):
    if not url:
        return False

    parsed = urlparse(
        url
    )

    host = (
        parsed.netloc
        .lower()
        .split(":")[0]
    )

    path = (
        parsed.path
        .lower()
    )

    if (
        host in {
            "www.facebook.com",
            "facebook.com",
        }
        and (
            path.startswith(
                "/sharer/"
            )
            or path.startswith(
                "/sharer.php"
            )
            or path.startswith(
                "/dialog/share"
            )
        )
    ):
        return True

    if (
        host in {
            "twitter.com",
            "www.twitter.com",
            "x.com",
            "www.x.com",
        }
        and (
            path.startswith(
                "/intent/tweet"
            )
            or path.startswith(
                "/share"
            )
        )
    ):
        return True

    if (
        host in {
            "social-plugins.line.me",
            "timeline.line.me",
            "line.me",
            "www.line.me",
        }
        and (
            path.startswith(
                "/lineit/"
            )
            or path.startswith(
                "/r/msg/"
            )
            or path.startswith(
                "/social-plugin/share"
            )
        )
    ):
        return True

    return False


# ==========================================================
# Schedule一覧へ戻るリンク判定
# ==========================================================

def is_schedule_back_link(
    url,
    label="",
):
    if not url:
        return False

    parsed = urlparse(
        url
    )

    host = (
        parsed.netloc
        .lower()
        .split(":")[0]
    )

    path = (
        parsed.path
        .rstrip("/")
        .lower()
    )

    normalized_label = (
        clean_text(
            label
        ).lower()
    )

    if (
        host in {
            "ini-official.com",
            "www.ini-official.com",
        }
        and path == "/schedule/list"
        and normalized_label == "back"
    ):
        return True

    return False


# ==========================================================
# 外部リンク
# ==========================================================

def extract_external_links(
    content_element,
    detail_url,
):
    links = []

    seen = set()

    for link in (
        content_element.find_all(
            "a",
            href=True,
        )
    ):
        href = absolute_url(
            detail_url,
            link.get(
                "href",
                "",
            ),
        )

        href = normalize_url(
            href
        )

        if not href:
            continue

        parsed = urlparse(
            href
        )

        if parsed.scheme not in {
            "http",
            "https",
        }:
            continue

        if (
            normalize_url(
                detail_url
            )
            == href
        ):
            continue

        if is_social_share_url(
            href
        ):
            continue

        label = clean_text(
            link.get_text(
                " ",
                strip=True,
            )
        )

        if is_schedule_back_link(
            href,
            label,
        ):
            continue

        if href in seen:
            continue

        seen.add(
            href
        )

        links.append(
            {
                "label": label,
                "url": href,
            }
        )

    return links


# ==========================================================
# 詳細ページ解析
# ==========================================================

def fetch_schedule_detail(
    entry,
):
    detail_url = entry[
        "url"
    ]

    html, final_url = (
        fetch_html(
            detail_url
        )
    )

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    (
        content_element,
        detail_text,
    ) = find_detail_content(
        soup
    )

    detail_text = (
        clean_schedule_detail_text(
            detail_text
        )
    )

    (
        date,
        category,
        category_label,
        title,
    ) = extract_detail_header(
        soup,
        entry,
    )

    member_search_text = (
        f"{title}\n{detail_text}"
    )

    members = extract_members(
        member_search_text
    )

    external_links = (
        extract_external_links(
            content_element,
            final_url,
        )
    )

    result = dict(
        entry
    )

    result.update(
        {
            "date": (
                date
                or entry.get(
                    "date",
                    ""
                )
            ),
            "category": category,
            "categoryLabel": (
                category_label
            ),
            "title": (
                title
                or entry.get(
                    "title",
                    ""
                )
            ),
            "url": normalize_url(
                final_url
            ),
            "members": members,
            "externalLinks": (
                external_links
            ),
            "detailText": (
                detail_text
            ),
        }
    )

    return result


# ==========================================================
# 1か月取得
# ==========================================================

def fetch_month(
    year,
    month,
):
    list_url = (
        SCHEDULE_LIST_URL.format(
            year=year,
            month=month,
        )
    )

    print()
    print("=" * 80)
    print(
        f"{year}-{month:02d}"
    )
    print("=" * 80)

    try:
        html, final_url = (
            fetch_html(
                list_url
            )
        )

    except Exception as error:
        print(
            "ERROR:",
            "一覧ページ取得失敗:",
            repr(error),
        )

        return None

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    entries = find_schedule_entries(
        soup,
        final_url,
        year,
        month,
    )

    print(
        "一覧:",
        len(entries),
        "件"
    )

    results = []

    for index, entry in enumerate(
        entries,
        start=1,
    ):
        print(
            f"  [{index}/{len(entries)}]",
            entry["date"],
            entry["categoryLabel"],
            entry["title"][:80],
        )

        try:
            detail = (
                fetch_schedule_detail(
                    entry
                )
            )

            results.append(
                detail
            )

        except Exception as error:
            print(
                "    WARNING:",
                "詳細取得失敗:",
                repr(error),
            )

            fallback = dict(
                entry
            )

            fallback.update(
                {
                    "members": [],
                    "externalLinks": [],
                    "detailText": "",
                }
            )

            results.append(
                fallback
            )

        time.sleep(
            REQUEST_INTERVAL
        )

    return results


# ==========================================================
# 既存JSON読込
# ==========================================================

def load_existing_items():
    if not OUTPUT_PATH.exists():
        print(
            "既存のschedule.jsonがありません。"
        )

        return []

    try:
        with OUTPUT_PATH.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(
                file
            )

    except Exception as error:
        raise RuntimeError(
            "既存のdata/schedule.jsonを"
            "読み込めませんでした。"
        ) from error

    if not isinstance(
        data,
        list,
    ):
        raise RuntimeError(
            "既存のdata/schedule.jsonが"
            "配列ではありません。"
        )

    print(
        "既存Schedule:",
        len(data),
        "件"
    )

    return data


# ==========================================================
# 重複排除
#
# scheduleIdをSchedule固有IDとして使用する。
# 同じscheduleIdが再取得された場合は、
# 新しく取得した内容で置き換える。
# ==========================================================

def deduplicate(items):
    result = {}

    for item in items:
        schedule_id = (
            item.get(
                "scheduleId"
            )
        )

        if not schedule_id:
            continue

        result[
            str(schedule_id)
        ] = item

    return list(
        result.values()
    )


# ==========================================================
# 更新対象月判定
# ==========================================================

def is_in_refresh_range(
    item,
    start_year,
    start_month,
    end_year,
    end_month,
):
    date = item.get(
        "date",
        "",
    )

    match = re.match(
        r"^(\d{4})-(\d{2})-\d{2}$",
        date,
    )

    if not match:
        # 日付が壊れている既存データは
        # 勝手に削除しない。
        return False

    year = int(
        match.group(1)
    )

    month = int(
        match.group(2)
    )

    value = (
        year * 12
        + month
    )

    start_value = (
        start_year * 12
        + start_month
    )

    end_value = (
        end_year * 12
        + end_month
    )

    return (
        start_value
        <= value
        <= end_value
    )


# ==========================================================
# 並び替え
# ==========================================================

CATEGORY_ORDER = {
    "release": 1,
    "live_event": 2,
    "tv": 3,
    "radio": 4,
    "magazine": 5,
    "web_media": 6,
    "birthday": 7,
    "other": 8,
}


def sort_key(item):
    return (
        item.get(
            "date",
            ""
        ),
        CATEGORY_ORDER.get(
            item.get(
                "category",
                "other",
            ),
            99,
        ),
        item.get(
            "title",
            ""
        ),
        item.get(
            "scheduleId",
            ""
        ),
    )


# ==========================================================
# 保存
# ==========================================================

def save_json(items):
    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            items,
            file,
            ensure_ascii=False,
            indent=2,
        )

        file.write(
            "\n"
        )


# ==========================================================
# 実行
# ==========================================================

def main():
    now = datetime.now()

    start_year, start_month = (
        add_months(
            now.year,
            now.month,
            -REFRESH_PAST_MONTHS,
        )
    )

    end_year, end_month = (
        add_months(
            now.year,
            now.month,
            FUTURE_MONTHS,
        )
    )

    print("=" * 80)
    print("INI Schedule incremental fetch")
    print("=" * 80)

    print(
        "更新対象:",
        f"{start_year}-{start_month:02d}",
        "〜",
        f"{end_year}-{end_month:02d}",
    )

    print(
        "出力:",
        OUTPUT_PATH,
    )

    # ------------------------------------------------------
    # 既存データを読み込む
    # ------------------------------------------------------

    existing_items = (
        load_existing_items()
    )

    # ------------------------------------------------------
    # 更新対象期間より古いデータは、
    # HTTPアクセスせずそのまま保持する。
    # ------------------------------------------------------

    preserved_items = [
        item
        for item in existing_items
        if not is_in_refresh_range(
            item,
            start_year,
            start_month,
            end_year,
            end_month,
        )
    ]

    refresh_old_items = [
        item
        for item in existing_items
        if is_in_refresh_range(
            item,
            start_year,
            start_month,
            end_year,
            end_month,
        )
    ]

    print(
        "そのまま保持:",
        len(preserved_items),
        "件"
    )

    print(
        "再取得対象だった既存データ:",
        len(refresh_old_items),
        "件"
    )

    # ------------------------------------------------------
    # 直近〜将来分だけ公式サイトから再取得
    # ------------------------------------------------------

    refreshed_items = []

    successful_months = set()
    failed_months = set()

    for year, month in iter_months(
        start_year,
        start_month,
        end_year,
        end_month,
    ):
        month_items = (
            fetch_month(
                year,
                month,
            )
        )

        key = month_key(
            year,
            month,
        )

        if month_items is None:
            failed_months.add(
                key
            )

            print(
                "WARNING:",
                key,
                "の一覧取得に失敗したため、"
                "既存データを保持します。"
            )

        else:
            successful_months.add(
                key
            )

            refreshed_items.extend(
                month_items
            )

        time.sleep(
            REQUEST_INTERVAL
        )

    # ------------------------------------------------------
    # 月一覧の取得に失敗した月については、
    # 既存JSONのデータを消さず保持する。
    # ------------------------------------------------------

    failed_month_existing = []

    for item in refresh_old_items:
        date = item.get(
            "date",
            "",
        )

        item_month = (
            date[:7]
            if len(date) >= 7
            else ""
        )

        if (
            item_month
            in failed_months
        ):
            failed_month_existing.append(
                item
            )

    # ------------------------------------------------------
    # マージ
    #
    # 1. 更新対象外の過去データ
    # 2. 取得失敗月の既存データ
    # 3. 正常に再取得できた最新データ
    #
    # の順で入れる。
    # scheduleIdが重複した場合は後のデータが優先。
    # ------------------------------------------------------

    all_items = []

    all_items.extend(
        preserved_items
    )

    all_items.extend(
        failed_month_existing
    )

    all_items.extend(
        refreshed_items
    )

    all_items = deduplicate(
        all_items
    )

    all_items.sort(
        key=sort_key
    )

    # ------------------------------------------------------
    # 安全チェック
    #
    # 既存データがあるのに、何らかの不具合で
    # 全体件数が極端に減った場合は保存しない。
    # ------------------------------------------------------

    if existing_items:
        minimum_safe_count = int(
            len(existing_items)
            * 0.90
        )

        if (
            len(all_items)
            < minimum_safe_count
        ):
            raise RuntimeError(
                "更新後のSchedule件数が"
                "既存データの90%未満になりました。"
                "データ消失防止のため保存を中止します。"
                f" existing={len(existing_items)}"
                f" new={len(all_items)}"
            )

    save_json(
        all_items
    )

    print()
    print("=" * 80)
    print("完了")
    print("=" * 80)

    print(
        "既存Schedule:",
        len(existing_items),
        "件"
    )

    print(
        "保持した過去データ:",
        len(preserved_items),
        "件"
    )

    print(
        "今回再取得:",
        len(refreshed_items),
        "件"
    )

    print(
        "取得失敗月から保持:",
        len(failed_month_existing),
        "件"
    )

    print(
        "最終Schedule:",
        len(all_items),
        "件"
    )

    print(
        "正常取得月:",
        len(successful_months),
    )

    print(
        "取得失敗月:",
        len(failed_months),
    )

    if failed_months:
        print(
            "失敗した月:",
            ", ".join(
                sorted(
                    failed_months
                )
            ),
        )

    if all_items:
        print()
        print("最古:")
        print(
            json.dumps(
                all_items[0],
                ensure_ascii=False,
                indent=2,
            )
        )

        print()
        print("最新:")
        print(
            json.dumps(
                all_items[-1],
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
