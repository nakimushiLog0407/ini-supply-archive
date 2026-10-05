#!/usr/bin/env python3

import json
import os
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


def load_datasets():
    datasets = {}

    for name, path in (
        matcher.DATA_FILES.items()
    ):
        datasets[name] = (
            matcher.load_json(path)
        )

        print(
            f"{name}: "
            f"{len(datasets[name])}"
        )

    return datasets


def serialize_match(match):
    if not match:
        return None

    return {
        "sourceType": (
            match.get(
                "source_type"
            )
        ),
        "id": (
            match.get("id")
        ),
        "date": (
            match.get("date")
        ),
        "title": (
            match.get("title")
        ),
        "url": (
            match.get("url")
        ),
        "score": (
            match.get("score")
        ),
        "filterReason": (
            match.get(
                "filter_reason"
            )
        ),
        "identityMatch": (
            match.get(
                "identity_match"
            )
        ),
        "memberConflict": (
            match.get(
                "member_conflict"
            )
        ),
        "reasons": (
            match.get(
                "reasons",
                [],
            )
        ),
    }


def build_suggestion(
    detected,
    matches,
    group_key,
):
    result = matcher.classify_result(
        detected,
        matches,
    )

    top_match = (
        matches[0]
        if matches
        else None
    )

    if (
        result
        == "existing_content_candidate"
        and top_match
    ):
        return {
            "action": "link_existing",
            "targetType": (
                top_match[
                    "source_type"
                ]
            ),
            "targetId": (
                top_match["id"]
            ),
            "groupKey": (
                group_key
            ),
        }

    if (
        result
        == "new_schedule_candidate"
    ):
        return {
            "action": "new_schedule",
            "targetType": None,
            "targetId": None,
            "groupKey": (
                group_key
            ),
        }

    if (
        result
        == "x_content_candidate"
    ):
        return {
            "action": "new_x_content",
            "targetType": None,
            "targetId": None,
            "groupKey": (
                group_key
            ),
        }

    if (
        result
        == "exclude_candidate"
    ):
        return {
            "action": "exclude",
            "targetType": None,
            "targetId": None,
            "groupKey": (
                group_key
            ),
        }

    if (
        result
        == "unsupported_fc_content"
    ):
        return {
            "action": "review",
            "targetType": (
                "fc_content"
            ),
            "targetId": None,
            "groupKey": (
                group_key
            ),
            "reason": (
                "unsupported_fc_content"
            ),
        }

    return {
        "action": "review",
        "targetType": None,
        "targetId": None,
        "groupKey": (
            group_key
        ),
        "reason": result,
    }


def build_candidate(
    post,
    detected,
    matches,
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
            matches,
            group_key,
        )
    )

    result = (
        matcher.classify_result(
            detected,
            matches,
        )
    )

    members = (
        matcher.extract_members(
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

    video_keywords = []

    if detected["type"] in {
        "video",
        "sns",
    }:
        video_keywords = (
            matcher.extract_video_keywords(
                post["text"]
            )
        )

    strong_keywords = []
    weak_keywords = []

    if video_keywords:
        (
            strong_keywords,
            weak_keywords,
        ) = (
            matcher.split_video_keywords(
                video_keywords
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
            "strongVideoKeywords": (
                strong_keywords
            ),
            "weakVideoKeywords": (
                weak_keywords
            ),
        },

        "automaticResult": (
            result
        ),

        "suggestion": (
            suggestion
        ),

        "matches": [
            serialize_match(
                match
            )
            for match
            in matches
        ],

        "review": {
            "status": "pending",
            "action": None,
            "targetType": None,
            "targetId": None,
            "note": None,
        },
    }


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
        "LOAD DATASETS"
    )

    datasets = (
        load_datasets()
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
                    post["text"]
                )
            )

            matches = (
                matcher.find_matches(
                    post,
                    detected,
                    datasets,
                )
            )

            candidate = (
                build_candidate(
                    post,
                    detected,
                    matches,
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
                "  RESULT:",
                candidate[
                    "automaticResult"
                ],
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
