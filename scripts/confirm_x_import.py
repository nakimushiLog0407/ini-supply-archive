#!/usr/bin/env python3

import json
import os
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


CANDIDATES_FILE = Path("data/x_import_candidates.json")
X_CONTENTS_FILE = Path("data/x_contents.json")
EXCLUDED_FILE = Path("data/x_excluded.json")

ALLOWED_ACTIONS = {
    "new_x_content",
    "exclude",
    "skip",
}

JST = ZoneInfo("Asia/Tokyo")


def load_json(path, default):
    if not path.exists():
        return deepcopy(default)

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, type(default)):
        raise ValueError(
            f"{path} has invalid top-level type."
        )

    return data


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
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

    data = json.loads(raw)

    if not isinstance(data, list) or not data:
        raise ValueError(
            "APPROVALS_JSON must be "
            "a non-empty JSON array."
        )

    return data


def candidate_map(candidates):
    result = {}

    for candidate in candidates:
        post_id = str(
            candidate.get("postId", "")
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

        result[post_id] = candidate

    return result


def normalize_post_ids(value):
    if not isinstance(value, list) or not value:
        raise ValueError(
            "Each approval requires "
            "a non-empty postIds array."
        )

    post_ids = [
        str(item).strip()
        for item in value
    ]

    if (
        any(not post_id for post_id in post_ids)
        or len(post_ids) != len(set(post_ids))
    ):
        raise ValueError(
            "postIds contains empty "
            "or duplicate values."
        )

    return post_ids


def make_x_post(candidate):
    return {
        "postId": str(candidate["postId"]),
        "url": candidate.get("url") or "",
        "postedAt": candidate.get("postedAt"),
        "author": candidate.get("author"),
        "text": candidate.get("text") or "",
        "media": candidate.get("media") or [],
        "members": (
            (candidate.get("detected") or {})
            .get("members")
            or []
        ),
    }


def registered_post_ids(x_contents, excluded):
    result = set()

    for item in x_contents:
        posts = item.get("posts")

        if isinstance(posts, list):
            for post in posts:
                post_id = str(
                    post.get("postId", "")
                ).strip()
                if post_id:
                    result.add(post_id)
        else:
            # 旧形式が残っていても重複登録を防ぐ。
            post_id = str(
                item.get("postId", "")
            ).strip()
            if post_id:
                result.add(post_id)

    for item in excluded:
        post_id = str(
            item.get("postId", "")
        ).strip()
        if post_id:
            result.add(post_id)

    return result


def approval_title(approval, candidates):
    title = str(
        approval.get("title") or ""
    ).strip()

    if title:
        return title

    if len(candidates) > 1:
        raise ValueError(
            "Grouped new_x_content requires title."
        )

    detected = (
        candidates[0].get("detected")
        or {}
    )

    detected_title = str(
        detected.get("title") or ""
    ).strip()

    if detected_title:
        return detected_title

    text = str(
        candidates[0].get("text")
        or ""
    )

    first_line = (
        text.splitlines()[0]
        if text.splitlines()
        else ""
    ).strip()

    return first_line[:120] or "X"


def add_x_content(
    x_contents,
    approval,
    candidates,
):
    posts = [
        make_x_post(candidate)
        for candidate in candidates
    ]

    posts.sort(
        key=lambda post: (
            post.get("postedAt") or "",
            post.get("postId") or "",
        )
    )

    representative = posts[0]

    dates = {
        str(post.get("postedAt") or "")[:10]
        for post in posts
        if post.get("postedAt")
    }

    if len(dates) != 1:
        raise ValueError(
            "Grouped X posts must share "
            "the same posted date."
        )

    date = next(iter(dates))

    members = []
    seen_members = set()

    for post in posts:
        for member in post.get(
            "members",
            [],
        ):
            member = str(member).strip()
            if (
                member
                and member not in seen_members
            ):
                members.append(member)
                seen_members.add(member)

    item_id = (
        "x-"
        + representative["postId"]
    )

    if any(
        str(item.get("id", "")) == item_id
        for item in x_contents
    ):
        raise ValueError(
            f"X content already exists: {item_id}"
        )

    item = {
        "id": item_id,
        "type": "x",
        "date": date,
        "postedAt": representative.get(
            "postedAt"
        ),
        "title": approval_title(
            approval,
            candidates,
        ),
        "members": members,
        "posts": posts,
        "source": "x",
    }

    x_contents.append(item)

    return item_id


def add_excluded(excluded, candidate):
    excluded.append({
        "postId": str(candidate["postId"]),
        "url": candidate.get("url") or "",
        "postedAt": candidate.get("postedAt"),
        "text": candidate.get("text") or "",
    })


def mark_confirmed(
    candidate,
    approval,
    target_type=None,
    target_id=None,
):
    review = candidate.setdefault(
        "review",
        {},
    )

    review.update({
        "status": "confirmed",
        "action": approval["action"],
        "targetType": target_type,
        "targetId": target_id,
        "note": approval.get("note"),
        "confirmedAt": datetime.now(
            JST
        ).isoformat(timespec="seconds"),
    })


def main():
    candidates = load_json(
        CANDIDATES_FILE,
        [],
    )
    candidates_by_id = candidate_map(
        candidates
    )
    approvals = parse_approvals()

    x_contents = load_json(
        X_CONTENTS_FILE,
        [],
    )
    excluded = load_json(
        EXCLUDED_FILE,
        [],
    )

    registered = registered_post_ids(
        x_contents,
        excluded,
    )

    validated = []
    seen = set()

    # Phase 1: 全入力を検証する。
    for raw in approvals:
        if not isinstance(raw, dict):
            raise ValueError(
                "Each approval must be an object."
            )

        approval = deepcopy(raw)
        action = approval.get("action")

        if action not in ALLOWED_ACTIONS:
            raise ValueError(
                f"Unsupported action: {action}"
            )

        post_ids = normalize_post_ids(
            approval.get("postIds")
        )

        for post_id in post_ids:
            if post_id in seen:
                raise ValueError(
                    "postId appears in "
                    "multiple approvals: "
                    f"{post_id}"
                )
            seen.add(post_id)

            if post_id not in candidates_by_id:
                raise ValueError(
                    "Unknown candidate "
                    f"postId: {post_id}"
                )

            candidate = candidates_by_id[
                post_id
            ]

            status = (
                candidate.get("review")
                or {}
            ).get("status", "pending")

            if status != "pending":
                raise ValueError(
                    "Candidate is not pending: "
                    f"{post_id} ({status})"
                )

            if (
                action != "skip"
                and post_id in registered
            ):
                raise ValueError(
                    "postId already registered: "
                    f"{post_id}"
                )

        selected = [
            candidates_by_id[post_id]
            for post_id in post_ids
        ]

        if action == "new_x_content":
            # 複数投稿を1供給にまとめる場合は
            # DETAIL表示用タイトルを必須とする。
            approval_title(
                approval,
                selected,
            )

            dates = {
                str(
                    candidate.get("postedAt")
                    or ""
                )[:10]
                for candidate in selected
                if candidate.get("postedAt")
            }

            if len(dates) != 1:
                raise ValueError(
                    "Grouped X posts must share "
                    "the same posted date."
                )

        validated.append(
            (approval, post_ids)
        )

    # Phase 2: コピーだけを変更する。
    new_candidates = deepcopy(candidates)
    new_candidate_map = candidate_map(
        new_candidates
    )
    new_x_contents = deepcopy(
        x_contents
    )
    new_excluded = deepcopy(excluded)

    for approval, post_ids in validated:
        selected = [
            new_candidate_map[post_id]
            for post_id in post_ids
        ]

        action = approval["action"]

        if action == "skip":
            continue

        target_type = None
        target_id = None

        if action == "new_x_content":
            target_type = "x"
            target_id = add_x_content(
                new_x_contents,
                approval,
                selected,
            )

        elif action == "exclude":
            target_type = "excluded"

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

    new_x_contents.sort(
        key=lambda item: (
            item.get("postedAt") or "",
            item.get("id") or "",
        )
    )

    new_excluded.sort(
        key=lambda item: (
            item.get("postedAt") or "",
            item.get("postId") or "",
        )
    )

    # Phase 3: 全処理成功後のみ保存する。
    save_json(
        X_CONTENTS_FILE,
        new_x_contents,
    )
    save_json(
        EXCLUDED_FILE,
        new_excluded,
    )
    save_json(
        CANDIDATES_FILE,
        new_candidates,
    )

    print(
        "=== CONFIRM X IMPORT COMPLETE ==="
    )
    print("Approvals:", len(validated))
    print(
        "X contents:",
        len(new_x_contents),
    )
    print(
        "Excluded:",
        len(new_excluded),
    )

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("ERROR:", exc)
        sys.exit(1)
