#!/usr/bin/env python3

import json
import os
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


CANDIDATES_FILE = Path(
    "data/x_import_candidates.json"
)

LINKS_FILE = Path(
    "data/content_x_links.json"
)

X_CONTENTS_FILE = Path(
    "data/x_contents.json"
)

EXCLUDED_FILE = Path(
    "data/x_excluded.json"
)

SCHEDULE_FILE = Path(
    "data/schedule.json"
)

JST = ZoneInfo("Asia/Tokyo")


ALLOWED_ACTIONS = {
    "link_existing",
    "new_schedule",
    "new_x_content",
    "exclude",
    "skip",
}


def load_json(path, default):
    if not path.exists():
        return deepcopy(default)

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def save_json(path, data):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )
        file.write("\n")


def parse_approvals():
    raw = os.environ.get(
        "APPROVALS_JSON",
        "",
    ).strip()

    if not raw:
        raise ValueError(
            "APPROVALS_JSON is empty."
        )

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "APPROVALS_JSON is not valid JSON: "
            f"{exc}"
        ) from exc

    if not isinstance(data, list):
        raise ValueError(
            "APPROVALS_JSON must be a JSON array."
        )

    return data


def candidate_map(candidates):
    result = {}

    for candidate in candidates:
        post_id = str(
            candidate.get(
                "postId",
                "",
            )
        )

        if post_id:
            result[post_id] = candidate

    return result


def validate_approval(
    approval,
    candidates_by_id,
):
    if not isinstance(
        approval,
        dict,
    ):
        raise ValueError(
            "Each approval must be an object."
        )

    post_ids = approval.get(
        "postIds"
    )

    if not isinstance(
        post_ids,
        list,
    ) or not post_ids:
        raise ValueError(
            "Each approval requires "
            "a non-empty postIds array."
        )

    post_ids = [
        str(post_id)
        for post_id
        in post_ids
    ]

    if len(post_ids) != len(
        set(post_ids)
    ):
        raise ValueError(
            "Duplicate postId inside approval."
        )

    for post_id in post_ids:
        if post_id not in candidates_by_id:
            raise ValueError(
                "Unknown candidate postId: "
                f"{post_id}"
            )

    action = approval.get(
        "action"
    )

    if action not in ALLOWED_ACTIONS:
        raise ValueError(
            "Unsupported action: "
            f"{action}"
        )

    if action == "link_existing":
        if not approval.get(
            "targetType"
        ):
            raise ValueError(
                "link_existing requires "
                "targetType."
            )

        if not approval.get(
            "targetId"
        ):
            raise ValueError(
                "link_existing requires "
                "targetId."
            )

    if action == "new_schedule":
        schedule = approval.get(
            "schedule"
        )

        if not isinstance(
            schedule,
            dict,
        ):
            raise ValueError(
                "new_schedule requires "
                "schedule object."
            )

        if not schedule.get(
            "date"
        ):
            raise ValueError(
                "new_schedule requires "
                "schedule.date."
            )

        if not schedule.get(
            "title"
        ):
            raise ValueError(
                "new_schedule requires "
                "schedule.title."
            )

    return post_ids


def validate_no_duplicate_approvals(
    approvals,
):
    seen = set()

    for approval in approvals:
        for post_id in approval[
            "_postIds"
        ]:
            if post_id in seen:
                raise ValueError(
                    "The same postId appears "
                    "in multiple approvals: "
                    f"{post_id}"
                )

            seen.add(post_id)


def validate_existing_target(
    target_type,
    target_id,
    candidates,
):
    for candidate in candidates:
        for match in candidate.get(
            "matches",
            [],
        ):
            if (
                match.get("sourceType")
                == target_type
                and match.get("id")
                == target_id
            ):
                return

    raise ValueError(
        "Target was not present in "
        "the candidate match data: "
        f"{target_type} / {target_id}"
    )


def make_x_post(candidate):
    return {
        "postId": candidate[
            "postId"
        ],
        "url": candidate[
            "url"
        ],
        "postedAt": candidate.get(
            "postedAt"
        ),
        "text": candidate.get(
            "text"
        ),
    }


def add_content_link(
    links,
    target_type,
    target_id,
    candidates,
):
    entry = None

    for item in links:
        if (
            item.get("targetType")
            == target_type
            and item.get("targetId")
            == target_id
        ):
            entry = item
            break

    if entry is None:
        entry = {
            "targetType": target_type,
            "targetId": target_id,
            "xPosts": [],
        }
        links.append(entry)

    existing_ids = {
        str(post.get("postId"))
        for post in entry.get(
            "xPosts",
            [],
        )
    }

    for candidate in candidates:
        post_id = str(
            candidate["postId"]
        )

        if post_id in existing_ids:
            continue

        entry["xPosts"].append(
            make_x_post(candidate)
        )

        existing_ids.add(post_id)


def make_x_content(candidate):
    detected = candidate.get(
        "detected",
        {}
    )

    return {
        "id": (
            "x-"
            + str(
                candidate[
                    "postId"
                ]
            )
        ),
        "type": "x",
        "date": (
            candidate.get(
                "postedAt",
                ""
            )[:10]
        ),
        "postedAt": candidate.get(
            "postedAt"
        ),
        "title": (
            detected.get(
                "title"
            )
        ),
        "members": (
            detected.get(
                "members",
                []
            )
        ),
        "text": candidate.get(
            "text"
        ),
        "url": candidate.get(
            "url"
        ),
        "postId": candidate.get(
            "postId"
        ),
    }


def add_x_content(
    x_contents,
    candidate,
):
    post_id = str(
        candidate["postId"]
    )

    for item in x_contents:
        if str(
            item.get("postId")
        ) == post_id:
            return

    x_contents.append(
        make_x_content(
            candidate
        )
    )


def add_excluded(
    excluded,
    candidate,
):
    post_id = str(
        candidate["postId"]
    )

    for item in excluded:
        if str(
            item.get("postId")
        ) == post_id:
            return

    excluded.append({
        "postId": (
            candidate["postId"]
        ),
        "url": (
            candidate["url"]
        ),
        "postedAt": (
            candidate.get(
                "postedAt"
            )
        ),
        "text": (
            candidate.get(
                "text"
            )
        ),
    })


def next_schedule_id(
    schedules,
):
    maximum = 0

    for item in schedules:
        item_id = str(
            item.get(
                "id",
                "",
            )
        )

        if not item_id.startswith(
            "schedule-"
        ):
            continue

        try:
            number = int(
                item_id.split(
                    "-",
                    1,
                )[1]
            )
        except ValueError:
            continue

        maximum = max(
            maximum,
            number,
        )

    return (
        f"schedule-{maximum + 1}"
    )


def add_new_schedule(
    schedules,
    links,
    approval,
    candidates,
):
    schedule_input = approval[
        "schedule"
    ]

    schedule_id = (
        next_schedule_id(
            schedules
        )
    )

    members = schedule_input.get(
        "members",
        []
    )

    if not isinstance(
        members,
        list,
    ):
        raise ValueError(
            "schedule.members "
            "must be an array."
        )

    schedule = {
        "id": schedule_id,
        "type": "schedule",
        "date": schedule_input[
            "date"
        ],
        "title": schedule_input[
            "title"
        ],
        "members": members,
        "detailText": (
            schedule_input.get(
                "detailText"
            )
            or ""
        ),
        "externalLinks": (
            schedule_input.get(
                "externalLinks"
            )
            or []
        ),
        "source": "x",
    }

    schedules.append(
        schedule
    )

    add_content_link(
        links,
        "schedule",
        schedule_id,
        candidates,
    )

    return schedule_id


def mark_candidate_confirmed(
    candidate,
    approval,
    target_id=None,
):
    review = candidate.setdefault(
        "review",
        {},
    )

    review[
        "status"
    ] = "confirmed"

    review[
        "action"
    ] = approval[
        "action"
    ]

    review[
        "targetType"
    ] = approval.get(
        "targetType"
    )

    review[
        "targetId"
    ] = (
        target_id
        or approval.get(
            "targetId"
        )
    )

    review[
        "note"
    ] = approval.get(
        "note"
    )

    review[
        "confirmedAt"
    ] = datetime.now(
        JST
    ).isoformat(
        timespec="seconds"
    )


def main():
    print(
        "=== CONFIRM X IMPORT ==="
    )

    candidates = load_json(
        CANDIDATES_FILE,
        [],
    )

    if not isinstance(
        candidates,
        list,
    ):
        print(
            "ERROR: candidate data "
            "must be an array."
        )
        return 1

    approvals = parse_approvals()

    candidates_by_id = (
        candidate_map(
            candidates
        )
    )

    validated = []

    for approval in approvals:
        copied = deepcopy(
            approval
        )

        copied[
            "_postIds"
        ] = validate_approval(
            copied,
            candidates_by_id,
        )

        validated.append(
            copied
        )

    validate_no_duplicate_approvals(
        validated
    )

    # ここまで一切書き込まない。
    # 全入力の検証に成功してから
    # メモリ上で変更を開始する。

    links = load_json(
        LINKS_FILE,
        [],
    )

    x_contents = load_json(
        X_CONTENTS_FILE,
        [],
    )

    excluded = load_json(
        EXCLUDED_FILE,
        [],
    )

    schedules = load_json(
        SCHEDULE_FILE,
        [],
    )

    confirmed_count = 0

    print(
        "Approvals:",
        len(validated),
    )

    for approval in validated:
        post_ids = approval[
            "_postIds"
        ]

        selected_candidates = [
            candidates_by_id[
                post_id
            ]
            for post_id
            in post_ids
        ]

        action = approval[
            "action"
        ]

        print()
        print(
            "ACTION:",
            action,
        )

        print(
            "POST IDS:",
            ", ".join(
                post_ids
            ),
        )

        target_id = None

        if action == "skip":
            print(
                "SKIPPED"
            )
            continue

        if action == "link_existing":
            target_type = approval[
                "targetType"
            ]

            target_id = approval[
                "targetId"
            ]

            validate_existing_target(
                target_type,
                target_id,
                selected_candidates,
            )

            add_content_link(
                links,
                target_type,
                target_id,
                selected_candidates,
            )

            print(
                "LINKED:",
                target_type,
                target_id,
            )

        elif action == "new_schedule":
            target_id = (
                add_new_schedule(
                    schedules,
                    links,
                    approval,
                    selected_candidates,
                )
            )

            print(
                "NEW SCHEDULE:",
                target_id,
            )

        elif action == "new_x_content":
            for candidate in (
                selected_candidates
            ):
                add_x_content(
                    x_contents,
                    candidate,
                )

            print(
                "NEW X CONTENT:",
                len(
                    selected_candidates
                ),
            )

        elif action == "exclude":
            for candidate in (
                selected_candidates
            ):
                add_excluded(
                    excluded,
                    candidate,
                )

            print(
                "EXCLUDED:",
                len(
                    selected_candidates
                ),
            )

        for candidate in (
            selected_candidates
        ):
            mark_candidate_confirmed(
                candidate,
                approval,
                target_id,
            )

            confirmed_count += 1

    # すべての処理が成功してから保存。
    save_json(
        LINKS_FILE,
        links,
    )

    save_json(
        X_CONTENTS_FILE,
        x_contents,
    )

    save_json(
        EXCLUDED_FILE,
        excluded,
    )

    save_json(
        SCHEDULE_FILE,
        schedules,
    )

    save_json(
        CANDIDATES_FILE,
        candidates,
    )

    print()
    print(
        "=== COMPLETE ==="
    )

    print(
        "Confirmed candidates:",
        confirmed_count,
    )

    print(
        "Content X links:",
        len(links),
    )

    print(
        "X contents:",
        len(x_contents),
    )

    print(
        "Excluded X posts:",
        len(excluded),
    )

    print(
        "Schedules:",
        len(schedules),
    )

    return 0


if __name__ == "__main__":
    try:
        sys.exit(
            main()
        )
    except Exception as exc:
        print(
            "ERROR:",
            exc,
        )
        sys.exit(1)
