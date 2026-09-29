import json
import os
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path


# ========================================
# 基本設定
# ========================================

API_KEY = os.environ.get("YOUTUBE_API_KEY")

# INI公式YouTubeチャンネル
CHANNEL_ID = "UCc-itdQHxLvUlPrDxIiSJrA"

# 現在使用しているYouTubeデータ
YOUTUBE_FILE = Path("data/youtube.json")


# ========================================
# YouTube API
# ========================================

def youtube_api(endpoint, params):
    params = dict(params)
    params["key"] = API_KEY

    query = urllib.parse.urlencode(params)

    url = (
        "https://www.googleapis.com/youtube/v3/"
        f"{endpoint}?{query}"
    )

    with urllib.request.urlopen(url) as response:
        return json.loads(
            response.read().decode("utf-8")
        )


# ========================================
# youtube.json を読み込む
# ========================================

def load_json_videos():
    if not YOUTUBE_FILE.exists():
        raise RuntimeError(
            "data/youtube.json が見つかりません。"
        )

    with YOUTUBE_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise RuntimeError(
            "data/youtube.json の形式が不正です。"
        )

    return data


# ========================================
# UploadsプレイリストIDを取得
# ========================================

def get_uploads_playlist_id():
    data = youtube_api(
        "channels",
        {
            "part": "contentDetails",
            "id": CHANNEL_ID,
        },
    )

    items = data.get("items", [])

    if not items:
        raise RuntimeError(
            "INI公式YouTubeチャンネルの"
            "情報を取得できませんでした。"
        )

    return (
        items[0]
        ["contentDetails"]
        ["relatedPlaylists"]
        ["uploads"]
    )


# ========================================
# 現在のUploadsプレイリストを全件取得
#
# status も取得して
# privacyStatus を確認する
# ========================================

def fetch_current_uploads(
    uploads_playlist_id,
):
    print(
        "現在のUploadsプレイリストを"
        "全件取得しています..."
    )

    videos = {}
    page_token = None

    while True:
        params = {
            "part": (
                "snippet,"
                "contentDetails,"
                "status"
            ),
            "playlistId": uploads_playlist_id,
            "maxResults": 50,
        }

        if page_token:
            params["pageToken"] = page_token

        data = youtube_api(
            "playlistItems",
            params,
        )

        for item in data.get("items", []):
            snippet = item.get(
                "snippet",
                {},
            )

            content_details = item.get(
                "contentDetails",
                {},
            )

            status = item.get(
                "status",
                {},
            )

            video_id = content_details.get(
                "videoId"
            )

            if not video_id:
                continue

            title = snippet.get(
                "title",
                ""
            )

            published_at = snippet.get(
                "publishedAt",
                ""
            )

            privacy_status = status.get(
                "privacyStatus",
                "unknown",
            )

            videos[video_id] = {
                "videoId": video_id,
                "title": title,
                "publishedAt": published_at,
                "privacyStatus": privacy_status,
            }

        page_token = data.get(
            "nextPageToken"
        )

        if not page_token:
            break

    return videos


# ========================================
# 診断結果を表示
# ========================================

def print_diagnostics(
    json_videos,
    current_uploads,
):
    # ------------------------------------
    # JSON側をvideoId単位で整理
    # ------------------------------------

    json_by_video_id = {}

    for video in json_videos:
        video_id = video.get(
            "videoId"
        )

        if not video_id:
            continue

        json_by_video_id[video_id] = video


    json_ids = set(
        json_by_video_id.keys()
    )

    current_ids = set(
        current_uploads.keys()
    )


    # ------------------------------------
    # 差分
    # ------------------------------------

    json_only_ids = (
        json_ids - current_ids
    )

    youtube_only_ids = (
        current_ids - json_ids
    )

    common_ids = (
        json_ids & current_ids
    )


    # ====================================
    # 公開状態を集計
    # ====================================

    privacy_counts = Counter(
        video.get(
            "privacyStatus",
            "unknown",
        )
        for video
        in current_uploads.values()
    )


    # ====================================
    # 基本集計
    # ====================================

    print()
    print("=" * 60)
    print("YouTubeデータ診断結果")
    print("=" * 60)

    print(
        f"youtube.json レコード数: "
        f"{len(json_videos)}"
    )

    print(
        f"youtube.json videoId数: "
        f"{len(json_ids)}"
    )

    print(
        f"現在のUploadsプレイリスト: "
        f"{len(current_ids)}"
    )

    print(
        f"両方に存在: "
        f"{len(common_ids)}"
    )

    print(
        f"JSONにだけ存在: "
        f"{len(json_only_ids)}"
    )

    print(
        f"Uploadsにだけ存在: "
        f"{len(youtube_only_ids)}"
    )

    print("=" * 60)


    # ====================================
    # 公開状態
    # ====================================

    print()
    print("【Uploadsプレイリストの公開状態】")
    print()

    print(
        f"public: "
        f"{privacy_counts.get('public', 0)}"
    )

    print(
        f"unlisted: "
        f"{privacy_counts.get('unlisted', 0)}"
    )

    print(
        f"private: "
        f"{privacy_counts.get('private', 0)}"
    )

    print(
        f"unknown: "
        f"{privacy_counts.get('unknown', 0)}"
    )


    # 上記4種類以外の値があれば表示
    standard_statuses = {
        "public",
        "unlisted",
        "private",
        "unknown",
    }

    other_statuses = {
        status: count
        for status, count
        in privacy_counts.items()
        if status not in standard_statuses
    }

    if other_statuses:
        print()
        print(
            "その他のprivacyStatus:"
        )

        for status, count in sorted(
            other_statuses.items()
        ):
            print(
                f"{status}: {count}"
            )


    print()
    print(
        "公開状態 合計: "
        f"{sum(privacy_counts.values())}"
    )

    print("=" * 60)


    # ====================================
    # public以外の動画
    # ====================================

    non_public_videos = [
        video
        for video
        in current_uploads.values()
        if (
            video.get(
                "privacyStatus",
                "unknown",
            )
            != "public"
        )
    ]

    non_public_videos.sort(
        key=lambda video: (
            video.get(
                "publishedAt",
                "",
            ),
            video.get(
                "videoId",
                "",
            ),
        )
    )


    print()
    print(
        "【public以外の動画】"
    )
    print()


    if not non_public_videos:
        print("なし")

    else:
        for index, video in enumerate(
            non_public_videos,
            start=1,
        ):
            video_id = video.get(
                "videoId",
                ""
            )

            print(
                f"{index}. "
                f"{video.get('title', '')}"
            )

            print(
                "   privacyStatus: "
                f"{video.get('privacyStatus', '')}"
            )

            print(
                f"   videoId: {video_id}"
            )

            print(
                "   publishedAt: "
                f"{video.get('publishedAt', '')}"
            )

            print(
                "   URL: "
                "https://www.youtube.com/watch?v="
                f"{video_id}"
            )

            print()


    # ====================================
    # JSONにだけ存在
    # ====================================

    print()
    print(
        "【JSONにあるが、現在のUploadsにはない動画】"
    )
    print()


    if not json_only_ids:
        print("なし")

    else:
        json_only_videos = [
            json_by_video_id[video_id]
            for video_id
            in json_only_ids
        ]

        json_only_videos.sort(
            key=lambda video: (
                video.get(
                    "publishedAt",
                    video.get(
                        "date",
                        "",
                    ),
                ),
                video.get(
                    "videoId",
                    "",
                ),
            )
        )

        for index, video in enumerate(
            json_only_videos,
            start=1,
        ):
            video_id = video.get(
                "videoId",
                ""
            )

            print(
                f"{index}. "
                f"{video.get('title', '')}"
            )

            print(
                f"   videoId: {video_id}"
            )

            print(
                "   date: "
                f"{video.get('date', '')}"
            )

            print(
                "   publishedAt: "
                f"{video.get('publishedAt', '')}"
            )

            print(
                "   URL: "
                "https://www.youtube.com/watch?v="
                f"{video_id}"
            )

            print()


    # ====================================
    # Uploadsにだけ存在
    # ====================================

    print()
    print(
        "【現在のUploadsにあるが、"
        "JSONにはない動画】"
    )
    print()


    if not youtube_only_ids:
        print("なし")

    else:
        youtube_only_videos = [
            current_uploads[video_id]
            for video_id
            in youtube_only_ids
        ]

        youtube_only_videos.sort(
            key=lambda video: (
                video.get(
                    "publishedAt",
                    "",
                ),
                video.get(
                    "videoId",
                    "",
                ),
            )
        )

        for index, video in enumerate(
            youtube_only_videos,
            start=1,
        ):
            video_id = video.get(
                "videoId",
                ""
            )

            print(
                f"{index}. "
                f"{video.get('title', '')}"
            )

            print(
                "   privacyStatus: "
                f"{video.get('privacyStatus', '')}"
            )

            print(
                f"   videoId: {video_id}"
            )

            print(
                "   publishedAt: "
                f"{video.get('publishedAt', '')}"
            )

            print(
                "   URL: "
                "https://www.youtube.com/watch?v="
                f"{video_id}"
            )

            print()


    print("=" * 60)

    print(
        "診断のみ実行しました。"
    )

    print(
        "youtube.jsonへの変更・削除は"
        "行っていません。"
    )

    print("=" * 60)


# ========================================
# メイン処理
# ========================================

def main():
    if not API_KEY:
        raise RuntimeError(
            "YOUTUBE_API_KEY が設定されていません。"
        )

    print(
        "youtube.jsonを読み込んでいます..."
    )

    json_videos = load_json_videos()

    print(
        f"JSONレコード数: "
        f"{len(json_videos)}件"
    )


    print(
        "INI公式YouTubeチャンネルを"
        "確認しています..."
    )

    uploads_playlist_id = (
        get_uploads_playlist_id()
    )


    current_uploads = (
        fetch_current_uploads(
            uploads_playlist_id
        )
    )


    print_diagnostics(
        json_videos,
        current_uploads,
    )


if __name__ == "__main__":
    main()
