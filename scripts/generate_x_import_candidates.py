#!/usr/bin/env python3

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import test_x_match as matcher


OUTPUT_FILE = Path(
    "data/x_import_candidates.json"
)

REQUEST_INTERVAL = 1.0


def load_existing_candidates():
    if not OUTPUT_FILE.exists():
        return []

    try:
        with OUTPUT_FILE.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if isinstance(data, list):
            return data

    except Exception as exc:
        print(
            "WARNING: "
            f"Could not read {OUTPUT_FILE}: "
            f"{exc}"
        )

    return []


def save_candidates(candidates):
    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            candidates,
            file,
            ensure_ascii=False,
            indent=2,
        )

        file.write("\n")


def build_suggestion(
    detected,
    group_key,
):
    # Xは他カテゴリーへ照合・紐付けせず、
    # X投稿そのものの判定だけで管理する。
    if detected["type"] == "exclude":
        action = "exclude"
    else:
        action = "new_x_content"

    return {
        "action": action,
        "targetType": None,
        "targetId": None,
        "groupKey": group_key,
    }


def build_candidate(
    post,
    detected,
):
    group_key = (
        matcher.detect_group_key(
            post,
            detected,
        )
    )

    suggestion = (
        build_suggestion(
            detected,
            group_key,
        )
    )


    # 本文冒頭の [#メンバー名] を投稿者として優先する。
    # 投稿種別やタイトルの判定には影響させない。
    leading_tag = re.match(
        r"^\s*\[#([^\]\n]+)\]",
        post["text"],
    )

    author_member = None

    if leading_tag:
        tag_name = leading_tag.group(1).strip()

        for canonical, aliases in (
            matcher.MEMBER_ALIASES.items()
        ):
            if (
                tag_name == canonical
                or tag_name in aliases
            ):
                author_member = canonical
                break

    members = (
        [author_member]
        if author_member
        else matcher.extract_members(
            post["text"]
        )
    )


    event_dates = (
        matcher.extract_event_dates(
            post["text"],
            post[
                "created_at_jst"
            ],
        )
    )

    extracted_title = (
        matcher.extract_fc_title(
            post["text"],
            detected["type"],
        )
    )

    schedule_names = []

    if (
        detected["type"]
        == "schedule"
    ):
        schedule_names = (
            matcher.extract_schedule_names(
                post["text"]
            )
        )

    posted_at = (
        post[
            "created_at_jst"
        ].isoformat()
        if post.get(
            "created_at_jst"
        )
        else None
    )

    return {
        "postId": (
            post["post_id"]
        ),
        "url": (
            post["url"]
        ),
        "postedAt": (
            posted_at
        ),
        "author": (
            post.get("author")
        ),
        "text": (
            post["text"]
        ),
        "media": (
            post.get("media")
            or []
        ),

        "detected": {
            "type": (
                detected["type"]
            ),
            "reason": (
                detected["reason"]
            ),
            "title": (
                extracted_title
            ),
            "members": (
                members
            ),
            "eventDates": [
                date.isoformat()
                for date
                in event_dates
            ],
            "scheduleNames": (
                schedule_names
            ),
        },


        "suggestion": (
            suggestion
        ),

        "review": {
            "status": "pending",
            "action": None,
            "targetType": None,
            "targetId": None,
            "note": None,
        },
    }



GENERIC_GROUP_HASHTAGS = {
    "ini",
    "mini",
    "アイエヌアイ",
}

# メンバー個人を示すタグは、同日の別シリーズでも
# 再利用されるためグループキーには使わない。
MEMBER_GROUP_HASHTAGS = {
    "池﨑理人", "ikezakirihito",
    "尾崎匠海", "ozakitakumi",
    "木村柾哉", "kimuramasaya",
    "後藤威尊", "gototakeru",
    "佐野雄大", "sanoyudai",
    "許豊凡", "xufengfan",
    "髙塚大夢", "takatsukahiromu",
    "田島将吾", "tajimashogo",
    "西洸人", "nishihiroto",
    "藤牧京介", "fujimakikyosuke",
    "松田迅", "matsudajin",
}


def extract_group_hashtags(text):
    result = []

    for value in re.findall(
        r"[#＃]([0-9A-Za-z_ぁ-んァ-ヶ一-龯髙﨑]+)",
        text or "",
    ):
        normalized = value.lower()

        if (
            normalized in GENERIC_GROUP_HASHTAGS
            or normalized in {
                value.lower()
                for value in MEMBER_GROUP_HASHTAGS
            }
        ):
            continue

        if normalized not in result:
            result.append(normalized)

    return result


def candidate_date(candidate):
    value = candidate.get("postedAt")

    if not value:
        return None

    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def candidate_datetime(candidate):
    value = candidate.get("postedAt")

    if not value:
        return None

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def set_group_suggestion(
    candidates,
    group_key,
    reason,
    proposed_title=None,
):
    post_ids = [
        str(item["postId"])
        for item in candidates
    ]

    for item in candidates:
        item["suggestion"]["groupKey"] = group_key
        item["groupSuggestion"] = {
            "groupKey": group_key,
            "reason": reason,
            "proposedTitle": proposed_title,
            "postIds": post_ids,
            "postCount": len(post_ids),
        }


def apply_group_suggestions(candidates):
    """
    X内だけのグループ候補を付ける。
    自動確定はせず、人間がConfirm時に最終判断する。

    優先1:
      同日・複数投稿で共有される特徴的なハッシュタグ。
      #INI / #MINI のような汎用タグは使わない。

    優先2:
      共通タグがなくても、同日に90分以内で連続し、
      各投稿が別々の1メンバーを含み、画像付きである場合は
      member_series としてレビュー候補にする。
    """

    assigned = set()

    hashtag_groups = {}

    for item in candidates:
        # 対象外候補は、共通ハッシュタグがあっても
        # X供給のグループ候補には含めない。
        if (
            item.get("suggestion", {}).get("action")
            == "exclude"
        ):
            continue

        date = candidate_date(item)

        if not date:
            continue

        for hashtag in extract_group_hashtags(
            item.get("text", "")
        ):
            hashtag_groups.setdefault(
                (date.isoformat(), hashtag),
                [],
            ).append(item)

    for (
        date_value,
        hashtag,
    ), items in hashtag_groups.items():
        # 2件程度の偶然の共通タグではまとめない。
        # メンバーシリーズのようなまとまりを想定し、
        # 3件以上をグループ候補の最低条件にする。
        if len(items) < 3:
            continue

        key = (
            f"hashtag:{date_value}:"
            f"{hashtag}"
        )

        set_group_suggestion(
            items,
            key,
            "shared_distinctive_hashtag",
            "#" + hashtag.upper(),
        )

        assigned.update(
            str(item["postId"])
            for item in items
        )

    by_date = {}

    for item in candidates:
        post_id = str(item["postId"])

        if (
            post_id in assigned
            or item.get("suggestion", {}).get("action")
            == "exclude"
        ):
            continue

        members = (
            item.get("detected", {})
            .get("members", [])
        )

        media = item.get("media") or []

        if (
            len(members) != 1
            or not any(
                value.get("type") == "photo"
                for value in media
                if isinstance(value, dict)
            )
        ):
            continue

        date = candidate_date(item)

        if not date:
            continue

        by_date.setdefault(
            date.isoformat(),
            [],
        ).append(item)

    for date_value, items in by_date.items():
        items.sort(
            key=lambda item: (
                item.get("postedAt") or "",
                str(item.get("postId") or ""),
            )
        )

        series = []

        def flush_series():
            nonlocal series

            if len(series) < 3:
                series = []
                return

            members = [
                item["detected"]["members"][0]
                for item in series
            ]

            if len(set(members)) != len(members):
                series = []
                return

            first_id = str(series[0]["postId"])

            set_group_suggestion(
                series,
                (
                    f"member_series:"
                    f"{date_value}:"
                    f"{first_id}"
                ),
                "same_day_close_time_distinct_members_with_photos",
                None,
            )

            series = []

        previous_dt = None

        for item in items:
            current_dt = candidate_datetime(item)

            if (
                previous_dt is not None
                and current_dt is not None
                and (
                    current_dt - previous_dt
                ).total_seconds()
                > 90 * 60
            ):
                flush_series()

            series.append(item)
            previous_dt = current_dt

        flush_series()

    return candidates


def merge_candidates(
    existing,
    generated,
):
    existing_by_id = {}

    for item in existing:
        post_id = str(
            item.get(
                "postId",
                "",
            )
        )

        if post_id:
            existing_by_id[
                post_id
            ] = item

    result = list(existing)

    added = 0
    updated_pending = 0
    preserved_reviewed = 0

    for candidate in generated:
        post_id = str(
            candidate["postId"]
        )

        old = (
            existing_by_id.get(
                post_id
            )
        )

        if old is None:
            result.append(
                candidate
            )

            existing_by_id[
                post_id
            ] = candidate

            added += 1
            continue

        old_review = (
            old.get("review")
            or {}
        )

        old_status = (
            old_review.get(
                "status"
            )
        )

        # 人間がすでに確認した候補は
        # 自動生成で上書きしない。
        if old_status not in {
            None,
            "",
            "pending",
        }:
            preserved_reviewed += 1
            continue

        # pendingなら最新の自動判定に更新する。
        index = result.index(old)

        # review欄にユーザーが途中入力した
        # note等があれば保持する。
        candidate[
            "review"
        ] = {
            "status": (
                old_review.get(
                    "status"
                )
                or "pending"
            ),
            "action": (
                old_review.get(
                    "action"
                )
            ),
            "targetType": (
                old_review.get(
                    "targetType"
                )
            ),
            "targetId": (
                old_review.get(
                    "targetId"
                )
            ),
            "note": (
                old_review.get(
                    "note"
                )
            ),
        }

        result[index] = candidate

        existing_by_id[
            post_id
        ] = candidate

        updated_pending += 1

    result.sort(
        key=lambda item: (
            item.get(
                "postedAt"
            )
            or "",
            item.get(
                "postId"
            )
            or "",
        )
    )

    return (
        result,
        added,
        updated_pending,
        preserved_reviewed,
    )


def main():
    matcher.section(
        "GENERATE X IMPORT CANDIDATES"
    )

    raw_urls = (
        os.environ.get(
            "X_URLS",
            "",
        ).strip()
    )

    if not raw_urls:
        print(
            "ERROR: X_URLS is empty"
        )
        return 1

    urls = (
        matcher.parse_urls(
            raw_urls
        )
    )

    if not urls:
        print(
            "ERROR: "
            "No valid X post URLs."
        )
        return 1

    print(
        "UNIQUE X POSTS:",
        len(urls),
    )

    matcher.section(
        "FETCH AND ANALYZE"
    )

    generated = []

    fetch_errors = 0

    for index, item in enumerate(
        urls,
        start=1,
    ):
        print()
        print(
            f"[{index}/{len(urls)}] "
            f"{item['post_id']}"
        )

        try:
            post = (
                matcher.fetch_post(
                    item
                )
            )

            if not post:
                print(
                    "  EMPTY"
                )
                fetch_errors += 1
                continue

            detected = (
                matcher.detect_post_type(
                    post["text"],
                    post.get("media"),
                )
            )

            candidate = (
                build_candidate(
                    post,
                    detected,
                )
            )

            generated.append(
                candidate
            )

            print(
                "  TYPE:",
                detected["type"],
            )

            print(
                "  SUGGESTION:",
                candidate[
                    "suggestion"
                ][
                    "action"
                ],
            )

            if (
                candidate[
                    "suggestion"
                ].get(
                    "targetId"
                )
            ):
                print(
                    "  TARGET:",
                    candidate[
                        "suggestion"
                    ][
                        "targetId"
                    ],
                )

            if (
                candidate[
                    "suggestion"
                ].get(
                    "groupKey"
                )
            ):
                print(
                    "  GROUP:",
                    candidate[
                        "suggestion"
                    ][
                        "groupKey"
                    ],
                )

        except Exception as exc:
            fetch_errors += 1

            print(
                "  ERROR:",
                exc,
            )

        if (
            index
            < len(urls)
        ):
            time.sleep(
                REQUEST_INTERVAL
            )

    if not generated:
        print()
        print(
            "ERROR: "
            "No candidates generated."
        )
        return 1

    # 1件でも取得・解析に失敗した場合は、候補ファイルを
    # 部分更新せず失敗させる。供給の取りこぼしを防ぐ。
    if fetch_errors:
        print()
        print(
            "ERROR: "
            f"{fetch_errors} of {len(urls)} X posts "
            "could not be fetched or analyzed. "
            "Candidate data was not updated."
        )
        return 1

    generated = apply_group_suggestions(
        generated
    )

    matcher.section(
        "GROUP SUGGESTIONS"
    )

    group_summary = {}

    for candidate in generated:
        group = candidate.get(
            "groupSuggestion"
        )

        if not group:
            continue

        group_summary[
            group["groupKey"]
        ] = group

    if not group_summary:
        print("(none)")
    else:
        for group in group_summary.values():
            print(
                group["groupKey"],
                "=>",
                group["postCount"],
                "posts / title:",
                group["proposedTitle"],
                "/ reason:",
                group["reason"],
            )

    matcher.section(
        "MERGE CANDIDATES"
    )

    existing = (
        load_existing_candidates()
    )

    (
        merged,
        added,
        updated_pending,
        preserved_reviewed,
    ) = merge_candidates(
        existing,
        generated,
    )

    save_candidates(
        merged
    )

    print(
        "EXISTING:",
        len(existing),
    )

    print(
        "GENERATED:",
        len(generated),
    )

    print(
        "ADDED:",
        added,
    )

    print(
        "UPDATED PENDING:",
        updated_pending,
    )

    print(
        "PRESERVED REVIEWED:",
        preserved_reviewed,
    )

    print(
        "FETCH ERRORS:",
        fetch_errors,
    )

    print(
        "TOTAL CANDIDATES:",
        len(merged),
    )

    print(
        "OUTPUT:",
        OUTPUT_FILE,
    )

    print()

    print(
        "Production content data "
        "was not modified."
    )

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )
