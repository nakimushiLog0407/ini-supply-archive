import json

from test_x_match import (
    fetch_post,
    normalize_x_url,
)


TEST_POSTS = [
    (
        "single image",
        "https://x.com/official__INI/status/2105206011653230876",
    ),
    (
        "multiple images",
        "https://x.com/official__INI/status/2105190916898308519",
    ),
    (
        "video",
        "https://x.com/official__INI/status/2105893039273328774",
    ),
]


def main():
    for label, url in TEST_POSTS:
        item = normalize_x_url(url)

        if not item:
            raise RuntimeError(
                f"Could not normalize URL: {url}"
            )

        post = fetch_post(item)

        if not post:
            raise RuntimeError(
                f"Could not fetch post: {url}"
            )

        media = post.get("media") or []

        print()
        print("=" * 72)
        print(f"TEST: {label}")
        print(f"POST: {url}")
        print(f"MEDIA COUNT: {len(media)}")
        print(
            json.dumps(
                media,
                ensure_ascii=False,
                indent=2,
            )
        )

        if not media:
            raise RuntimeError(
                f"No media extracted: {label}"
            )

        if label == "single image":
            assert len(media) == 1
            assert media[0]["type"] == "photo"
            assert media[0].get("url")

        elif label == "multiple images":
            assert len(media) >= 2
            assert all(
                entry["type"] == "photo"
                and entry.get("url")
                for entry in media
            )

        elif label == "video":
            assert len(media) >= 1
            video = media[0]
            assert video["type"] == "video"
            assert video.get("videoUrl")
            assert video.get("thumbnailUrl")

    print()
    print("ALL X MEDIA EXTRACTION TESTS PASSED")


if __name__ == "__main__":
    main()
