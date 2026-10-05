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

X_SCHEDULE_FILE = Path(
    "data/x_schedule.json"
)


TARGET_FILES = {
    "youtube": Path(
        "data/youtube.json"
    ),
    "member_diary": Path(
        "data/member_diary.json"
    ),
    "movie": Path(
        "data/movie.json"
    ),
    "radio": Path(
        "data/radio.json"
    ),
    "photo": Path(
        "data/photo.json"
    ),
    "message": Path(
        "data/message.json"
    ),
    "schedule": Path(
        "data/schedule.json"
    ),
}


ALLOWED_ACTIONS = {
    "link_existing",
    "new_schedule",
    "new_x_content",
    "exclude",
    "skip",
}


JST = ZoneInfo(
    "Asia/Tokyo"
)


def load_json(
    path,
    default,
):
    if not path.exists():
        return deepcopy(
            default
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(
            file
        )

    if not isinstance(
        data,
        type(default),
    ):
        raise ValueError(
            f"{path} has invalid "
            "top-level type."
        )

    return data


def save_json(
    path,
    data,
):
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

    data = json.loads(
        raw
    )

    if (
        not isinstance(
            data,
            list,
        )
        or not data
    ):
        raise ValueError(
            "APPROVALS_JSON must be "
            "a non-empty JSON array."
        )

    return data


def candidate_map(
    candidates,
):
    result = {}

    for candidate in candidates:
        post_id = str(
            candidate.get(
                "postId",
                "",
            )
        ).strip()

        if not post_id:
            raise ValueError(
                "Candidate without postId."
            )

        if post_id in result:
            raise ValueError(
                "Duplicate candidate "
                f"postId: {post_id}"
            )

        result[
            post_id
        ] = candidate

    return result


def normalize_post_ids(
    value,
):
    if (
        not isinstance(
            value,
            list,
        )
        or not value
    ):
        raise ValueError(
            "Each approval requires "
            "a non-empty postIds array."
        )

    post_ids = [
        str(item).strip()
        for item in value
    ]

    if (
        any(
            not post_id
            for post_id
            in post_ids
        )
        or len(post_ids)
        != len(set(post_ids))
    ):
        raise ValueError(
            "postIds contains empty "
            "or duplicate values."
        )

    return post_ids


def load_target_ids():
    result = {}

    for (
        target_type,
        path,
    ) in TARGET_FILES.items():
        rows = load_json(
            path,
            [],
        )

        result[
            target_type
        ] = {
            str(
                row.get(
                    "id",
                    "",
                )
            ).strip()
            for row in rows
            if str(
                row.get(
                    "id",
                    "",
                )
            ).strip()
        }

    result[
        "x_schedule"
    ] = {
        str(
            row.get(
                "id",
                "",
            )
        ).strip()
        for row in load_json(
            X_SCHEDULE_FILE,
            [],
        )
        if str(
            row.get(
                "id",
                "",
            )
        ).strip()
    }

    return result


def all_registered_post_ids(
    links,
    x_contents,
    excluded,
    x_schedules,
):
    locations = {}

    def add(
        post_id,
        location,
    ):
        post_id = str(
            post_id or ""
        ).strip()

        if post_id:
            locations.setdefault(
                post_id,
                set(),
            ).add(
                location
            )

    for entry in links:
        for post in entry.get(
            "xPosts",
            [],
        ):
            add(
                post.get(
                    "postId"
                ),
                "content_x_links",
            )

    for item in x_contents:
        add(
            item.get(
                "postId"
            ),
            "x_contents",
        )

    for item in excluded:
        add(
            item.get(
                "postId"
            ),
            "x_excluded",
        )

    for item in x_schedules:
        for post in item.get(
            "xPosts",
            [],
        ):
            add(
                post.get(
                    "postId"
                ),
                "x_schedule",
            )

    return locations


def make_x_post(
    candidate,
):
    return {
        "postId": str(
            candidate[
                "postId"
            ]
        ),
        "url": (
            candidate.get(
                "url"
            )
            or ""
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
            or ""
        ),
        "media": (
            candidate.get(
                "media"
            )
            or []
        ),
    }


def validate_group(
    candidates,
):
    if len(
        candidates
    ) <= 1:
        return

    group_keys = {
        str(
            (
                candidate.get(
                    "suggestion"
                )
                or {}
            ).get(
                "groupKey"
            )
            or ""
        ).strip()
        for candidate
        in candidates
    }

    if (
        ""
        in group_keys
        or len(
            group_keys
        )
        != 1
    ):
        raise ValueError(
            "Grouped new_schedule "
            "posts must share one "
            "non-empty groupKey."
        )


def validate_schedule_input(
    schedule,
):
    if not isinstance(
        schedule,
        dict,
    ):
        raise ValueError(
            "new_schedule requires "
            "schedule object."
        )

    date = str(
        schedule.get(
            "date"
        )
        or ""
    ).strip()

    title = str(
        schedule.get(
            "title"
        )
        or ""
    ).strip()

    if (
        not date
        or not title
    ):
        raise ValueError(
            "new_schedule requires "
            "schedule.date and "
            "schedule.title."
        )

    members = schedule.get(
        "members",
        [],
    )

    external_links = (
        schedule.get(
            "externalLinks",
            [],
        )
    )

    if not isinstance(
        members,
        list,
    ):
        raise ValueError(
            "schedule.members "
            "must be an array."
        )

    if not isinstance(
        external_links,
        list,
    ):
        raise ValueError(
            "schedule.externalLinks "
            "must be an array."
        )


def deterministic_schedule_ids(
    post_ids,
):
    representative = min(
        post_ids,
        key=lambda value: (
            int(value)
            if value.isdigit()
            else value
        ),
    )

    return (
        (
            "x-schedule-"
            + representative
        ),
        (
            "x-"
            + representative
        ),
    )


def add_content_link(
    links,
    target_type,
    target_id,
    candidates,
):
    entry = next(
        (
            item
            for item in links
            if (
                item.get(
                    "targetType"
                )
                == target_type
                and item.get(
                    "targetId"
                )
                == target_id
            )
        ),
        None,
    )

    if entry is None:
        entry = {
            "targetType": (
                target_type
            ),
            "targetId": (
                target_id
            ),
            "xPosts": [],
        }

        links.append(
            entry
        )

    if not isinstance(
        entry.get(
            "xPosts"
        ),
        list,
    ):
        raise ValueError(
            "Invalid xPosts for "
            f"{target_type}/"
            f"{target_id}"
        )

    known_ids = {
        str(
            post.get(
                "postId"
            )
        )
        for post
        in entry[
            "xPosts"
        ]
    }

    for candidate in candidates:
        post_id = str(
            candidate[
                "postId"
            ]
        )

        if post_id in known_ids:
            continue

        entry[
            "xPosts"
        ].append(
            make_x_post(
                candidate
            )
        )

        known_ids.add(
            post_id
        )


def add_x_content(
    x_contents,
    candidate,
):
    detected = (
        candidate.get(
            "detected"
        )
        or {}
    )

    text = (
        candidate.get(
            "text"
        )
        or ""
    )

    first_line = (
        text.splitlines()[0]
        if text.splitlines()
        else ""
    )

    item = {
        "id": (
            "x-"
            + str(
                candidate[
                    "postId"
                ]
            )
        ),
        "type": "x",
        "date": str(
            candidate.get(
                "postedAt"
            )
            or ""
        )[:10],
        "postedAt": (
            candidate.get(
                "postedAt"
            )
        ),
        "title": (
            detected.get(
                "title"
            )
            or first_line[:120]
        ),
        "members": (
            detected.get(
                "members"
            )
            or []
        ),
        "text": text,
        "url": (
            candidate.get(
                "url"
            )
            or ""
        ),
        "postId": str(
            candidate[
                "postId"
            ]
        ),
        "media": (
            candidate.get(
                "media"
            )
            or []
        ),
        "source": "x",
    }

    x_contents.append(
        item
    )


def add_excluded(
    excluded,
    candidate,
):
    excluded.append({
        "postId": str(
            candidate[
                "postId"
            ]
        ),
        "url": (
            candidate.get(
                "url"
            )
            or ""
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
            or ""
        ),
    })


def add_x_schedule(
    x_schedules,
    approval,
    candidates,
):
    schedule = approval[
        "schedule"
    ]

    post_ids = [
        str(
            candidate[
                "postId"
            ]
        )
        for candidate
        in candidates
    ]

    (
        item_id,
        schedule_id,
    ) = deterministic_schedule_ids(
        post_ids
    )

    if any(
        (
            str(
                item.get(
                    "id"
                )
            )
            == item_id
            or str(
                item.get(
                    "scheduleId"
                )
            )
            == schedule_id
        )
        for item
        in x_schedules
    ):
        raise ValueError(
            "X schedule already "
            f"exists: {item_id}"
        )

    item = {
        "id": item_id,
        "scheduleId": (
            schedule_id
        ),
        "type": "schedule",
        "group": "schedule",
        "category": str(
            schedule.get(
                "category"
            )
            or "web_media"
        ),
        "categoryLabel": str(
            schedule.get(
                "categoryLabel"
            )
            or "Web Media"
        ),
        "date": str(
            schedule[
                "date"
            ]
        ).strip(),
        "title": str(
            schedule[
                "title"
            ]
        ).strip(),
        "url": str(
            schedule.get(
                "url"
            )
            or ""
        ),
        "members": (
            schedule.get(
                "members"
            )
            or []
        ),
        "externalLinks": (
            schedule.get(
                "externalLinks"
            )
            or []
        ),
        "detailText": str(
            schedule.get(
                "detailText"
            )
            or ""
        ),
        "source": "x",
        "xPosts": [
            make_x_post(
                candidate
            )
            for candidate
            in candidates
        ],
    }

    x_schedules.append(
        item
    )

    return item_id


def mark_confirmed(
    candidate,
    approval,
    target_type=None,
    target_id=None,
):
    review = (
        candidate.setdefault(
            "review",
            {},
        )
    )

    review.update({
        "status": "confirmed",
        "action": (
            approval[
                "action"
            ]
        ),
        "targetType": (
            target_type
        ),
        "targetId": (
            target_id
        ),
        "note": (
            approval.get(
                "note"
            )
        ),
        "confirmedAt": (
            datetime.now(
                JST
            ).isoformat(
                timespec="seconds"
            )
        ),
    })


def main():
    candidates = load_json(
        CANDIDATES_FILE,
        [],
    )

    candidates_by_id = (
        candidate_map(
            candidates
        )
    )

    approvals = (
        parse_approvals()
    )

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

    x_schedules = load_json(
        X_SCHEDULE_FILE,
        [],
    )

    target_ids = (
        load_target_ids()
    )

    registered = (
        all_registered_post_ids(
            links,
            x_contents,
            excluded,
            x_schedules,
        )
    )

    validated = []
    seen = set()

    # --------------------------------
    # Phase 1
    # 全入力を検証する。
    # この段階では何も変更しない。
    # --------------------------------

    for raw in approvals:
        if not isinstance(
            raw,
            dict,
        ):
            raise ValueError(
                "Each approval "
                "must be an object."
            )

        approval = deepcopy(
            raw
        )

        action = approval.get(
            "action"
        )

        if action not in (
            ALLOWED_ACTIONS
        ):
            raise ValueError(
                "Unsupported action: "
                f"{action}"
            )

        post_ids = (
            normalize_post_ids(
                approval.get(
                    "postIds"
                )
            )
        )

        for post_id in post_ids:
            if post_id in seen:
                raise ValueError(
                    "postId appears in "
                    "multiple approvals: "
                    f"{post_id}"
                )

            seen.add(
                post_id
            )

            if (
                post_id
                not in
                candidates_by_id
            ):
                raise ValueError(
                    "Unknown candidate "
                    f"postId: {post_id}"
                )

            candidate = (
                candidates_by_id[
                    post_id
                ]
            )

            status = (
                (
                    candidate.get(
                        "review"
                    )
                    or {}
                ).get(
                    "status",
                    "pending",
                )
            )

            if status != "pending":
                raise ValueError(
                    "Candidate is not "
                    "pending: "
                    f"{post_id} "
                    f"({status})"
                )

            if (
                action != "skip"
                and post_id
                in registered
            ):
                locations = sorted(
                    registered[
                        post_id
                    ]
                )

                raise ValueError(
                    "postId already "
                    "registered in "
                    f"{locations}: "
                    f"{post_id}"
                )

        selected = [
            candidates_by_id[
                post_id
            ]
            for post_id
            in post_ids
        ]

        if (
            action
            == "link_existing"
        ):
            target_type = str(
                approval.get(
                    "targetType"
                )
                or ""
            ).strip()

            target_id = str(
                approval.get(
                    "targetId"
                )
                or ""
            ).strip()

            if (
                target_type
                not in target_ids
                or not target_id
            ):
                raise ValueError(
                    "Invalid "
                    "link_existing "
                    "targetType/"
                    "targetId."
                )

            if (
                target_id
                not in
                target_ids[
                    target_type
                ]
            ):
                raise ValueError(
                    "Target does not "
                    "exist: "
                    f"{target_type}/"
                    f"{target_id}"
                )

        elif (
            action
            == "new_schedule"
        ):
            validate_schedule_input(
                approval.get(
                    "schedule"
                )
            )

            validate_group(
                selected
            )

            (
                item_id,
                schedule_id,
            ) = (
                deterministic_schedule_ids(
                    post_ids
                )
            )

            if any(
                (
                    str(
                        item.get(
                            "id"
                        )
                    )
                    == item_id
                    or str(
                        item.get(
                            "scheduleId"
                        )
                    )
                    == schedule_id
                )
                for item
                in x_schedules
            ):
                raise ValueError(
                    "X schedule already "
                    f"exists: {item_id}"
                )

        validated.append(
            (
                approval,
                post_ids,
            )
        )

    # --------------------------------
    # Phase 2
    # 検証完了後、コピーだけを変更する。
    # --------------------------------

    new_candidates = deepcopy(
        candidates
    )

    new_candidate_map = (
        candidate_map(
            new_candidates
        )
    )

    new_links = deepcopy(
        links
    )

    new_x_contents = deepcopy(
        x_contents
    )

    new_excluded = deepcopy(
        excluded
    )

    new_x_schedules = deepcopy(
        x_schedules
    )

    for (
        approval,
        post_ids,
    ) in validated:
        selected = [
            new_candidate_map[
                post_id
            ]
            for post_id
            in post_ids
        ]

        action = approval[
            "action"
        ]

        target_type = None
        target_id = None

        if action == "skip":
            continue

        if (
            action
            == "link_existing"
        ):
            target_type = str(
                approval[
                    "targetType"
                ]
            )

            target_id = str(
                approval[
                    "targetId"
                ]
            )

            add_content_link(
                new_links,
                target_type,
                target_id,
                selected,
            )

        elif (
            action
            == "new_schedule"
        ):
            target_type = (
                "x_schedule"
            )

            target_id = (
                add_x_schedule(
                    new_x_schedules,
                    approval,
                    selected,
                )
            )

        elif (
            action
            == "new_x_content"
        ):
            target_type = "x"

            for candidate in selected:
                add_x_content(
                    new_x_contents,
                    candidate,
                )

        elif (
            action
            == "exclude"
        ):
            target_type = (
                "excluded"
            )

            for candidate in selected:
                add_excluded(
                    new_excluded,
                    candidate,
                )

        for candidate in selected:
            mark_confirmed(
                candidate,
                approval,
                target_type,
                target_id,
            )

    # --------------------------------
    # Phase 3
    # 全処理成功後のみ保存する。
    # --------------------------------

    save_json(
        LINKS_FILE,
        new_links,
    )

    save_json(
        X_CONTENTS_FILE,
        new_x_contents,
    )

    save_json(
        EXCLUDED_FILE,
        new_excluded,
    )

    save_json(
        X_SCHEDULE_FILE,
        new_x_schedules,
    )

    save_json(
        CANDIDATES_FILE,
        new_candidates,
    )

    print(
        "=== CONFIRM X IMPORT "
        "COMPLETE ==="
    )

    print(
        "Approvals:",
        len(
            validated
        ),
    )

    print(
        "Content X links:",
        len(
            new_links
        ),
    )

    print(
        "X contents:",
        len(
            new_x_contents
        ),
    )

    print(
        "Excluded:",
        len(
            new_excluded
        ),
    )

    print(
        "X schedules:",
        len(
            new_x_schedules
        ),
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
