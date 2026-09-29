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

    query = urllib.parse.urlencode(
        params,
        doseq=True,
    )

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
# チャンネル情報を取得
#
# ・UploadsプレイリストID
# ・statistics.videoCount
# ========================================

def get_channel_info():
    data = youtube_api(
        "channels",
        {
            "part": "contentDetails,statistics",
            "id": CHANNEL_ID,
        },
    )

    items = data.get("items", [])

    if not items:
        raise RuntimeError(
            "INI公式YouTubeチャンネルの"
            "情報を取得できませんでした。"
        )

    channel = items[0]

    uploads_playlist_id = (
        channel
        .get("contentDetails", {})
        .get("relatedPlaylists", {})
        .get("uploads")
    )

    video_count = (
        channel
        .get("statistics", {})
        .get("videoCount")
    )

    if not uploads_playlist_id:
        raise RuntimeError(
            "UploadsプレイリストIDを"
            "取得できませんでした。"
        )

    return {
        "uploadsPlaylistId": uploads_playlist_id,
        "videoCount": video_count,
    }


# ========================================
# 現在のUploadsプレイリストを全件取得
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

            videos[video_id] = {
                "videoId": video_id,
                "title": snippet.get(
                    "title",
                    "",
                ),
                "publishedAt": snippet.get(
                    "publishedAt",
                    "",
                ),
                "playlistPrivacyStatus": (
                    status.get(
                        "privacyStatus",
                        "unknown",
                    )
                ),
            }

        page_token = data.get(
            "nextPageToken"
        )

        if not page_token:
            break

    return videos


# ========================================
# リストを50件ずつに分割
#
# videos.list は最大50動画ずつ照会
# ========================================

def chunk_list(items, size):
    for index in range(
        0,
        len(items),
        size,
    ):
        yield items[
            index:index + size
        ]


# ========================================
# 動画本体を videos.list で全件照合
# ========================================

def fetch_video_resources(video_ids):
    print(
        "Uploadsにある動画IDを使って、"
        "動画本体を確認しています..."
    )

    video_resources = {}

    sorted_ids = sorted(video_ids)

    batches = list(
        chunk_list(
            sorted_ids,
            50,
        )
    )

    total_batches = len(batches)

    for batch_number, batch in enumerate(
        batches,
        start=1,
    ):
        print(
            f"動画本体を確認中: "
            f"{batch_number}/{total_batches}"
        )

        data = youtube_api(
            "videos",
            {
                "part": (
                    "snippet,"
                    "status,"
                    "contentDetails"
                ),
                "id": ",".join(batch),
                "maxResults": 50,
            },
        )

        for item in data.get(
            "items",
            [],
        ):
            video_id = item.get("id")

            if not video_id:
                continue

            snippet = item.get(
                "snippet",
                {},
            )

            status = item.get(
                "status",
                {},
            )

            content_details = item.get(
                "contentDetails",
                {},
            )

            video_resources[video_id] = {
                "videoId": video_id,

                "title": snippet.get(
                    "title",
                    "",
                ),

                "publishedAt": snippet.get(
                    "publishedAt",
                    "",
                ),

                # ここが今回特に重要
                # 動画本体の公開状態
                "privacyStatus": (
                    status.get(
                        "privacyStatus",
                        "unknown",
                    )
                ),

                # 念のため追加情報も取得
                "uploadStatus": (
                    status.get(
                        "uploadStatus",
                        "unknown",
                    )
                ),

                "embeddable": status.get(
                    "embeddable"
                ),

                "duration": (
                    content_details.get(
                        "duration",
                        "",
                    )
                ),
            }

    return video_resources


# ========================================
# 診断結果を表示
# ========================================

def print_diagnostics(
    json_videos,
    channel_info,
    current_uploads,
    video_resources,
):
    # ------------------------------------
    # JSON側
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

    uploads_ids = set(
        current_uploads.keys()
    )

    resource_ids = set(
        video_resources.keys()
    )


    # ------------------------------------
    # 差分
    # ------------------------------------

    json_only_ids = (
        json_ids - uploads_ids
    )

    uploads_only_ids = (
        uploads_ids - json_ids
    )

    # Uploadsには存在するが、
    # videos.listでは動画本体を
    # 取得できなかったID
    missing_resource_ids = (
        uploads_ids - resource_ids
    )

    # 逆方向も念のため確認
    unexpected_resource_ids = (
        resource_ids - uploads_ids
    )


    # ====================================
    # 動画本体の公開状態
    # ====================================

    video_privacy_counts = Counter(
        video.get(
            "privacyStatus",
            "unknown",
        )
        for video
        in video_resources.values()
    )


    # ====================================
    # 動画本体のuploadStatus
    # ====================================

    upload_status_counts = Counter(
        video.get(
            "uploadStatus",
            "unknown",
        )
        for video
        in video_resources.values()
    )


    # ====================================
    # 全体結果
    # ====================================

    print()
    print("=" * 70)
    print("YouTube 詳細診断結果")
    print("=" * 70)

    print(
        f"youtube.json レコード数: "
        f"{len(json_videos)}"
    )

    print(
        f"youtube.json videoId数: "
        f"{len(json_ids)}"
    )

    print(
        f"Uploadsプレイリスト: "
        f"{len(uploads_ids)}"
    )

    print(
        "チャンネル statistics.videoCount: "
        f"{channel_info.get('videoCount')}"
    )

    print(
        f"videos.listで取得できた動画本体: "
        f"{len(resource_ids)}"
    )

    print("=" * 70)


    # ====================================
    # JSONとUploadsの比較
    # ====================================

    print()
    print("【JSONとUploadsの比較】")
    print()

    print(
        f"JSONにだけ存在: "
        f"{len(json_only_ids)}"
    )

    print(
        f"Uploadsにだけ存在: "
        f"{len(uploads_only_ids)}"
    )


    # ====================================
    # 動画本体の公開状態
    # ====================================

    print()
    print(
        "【動画本体の privacyStatus】"
    )
    print()

    print(
        "public: "
        f"{video_privacy_counts.get('public', 0)}"
    )

    print(
        "unlisted: "
        f"{video_privacy_counts.get('unlisted', 0)}"
    )

    print(
        "private: "
        f"{video_privacy_counts.get('private', 0)}"
    )

    print(
        "unknown: "
        f"{video_privacy_counts.get('unknown', 0)}"
    )

    print(
        "合計: "
        f"{sum(video_privacy_counts.values())}"
    )


    # ====================================
    # uploadStatus
    # ====================================

    print()
    print(
        "【動画本体の uploadStatus】"
    )
    print()

    for status, count in sorted(
        upload_status_counts.items()
    ):
        print(
            f"{status}: {count}"
        )

    print(
        "合計: "
        f"{sum(upload_status_counts.values())}"
    )

    print("=" * 70)


    # ====================================
    # 動画本体を取得できなかったもの
    # ====================================

    print()
    print(
        "【Uploadsにはあるが、"
        "videos.listで動画本体を"
        "取得できなかった動画】"
    )
    print()


    if not missing_resource_ids:
        print("なし")

    else:
        missing_videos = [
            current_uploads[video_id]
            for video_id
            in missing_resource_ids
        ]

        missing_videos.sort(
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
            missing_videos,
            start=1,
        ):
            video_id = video.get(
                "videoId",
                "",
            )

            print(
                f"{index}. "
                f"{video.get('title', '')}"
            )

            print(
                f"   videoId: {video_id}"
            )

            print(
                "   Uploads側のprivacyStatus: "
                f"{video.get('playlistPrivacyStatus', '')}"
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
    # 動画本体でpublic以外
    # ====================================

    non_public_videos = [
        video
        for video
        in video_resources.values()
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
        "【動画本体でpublic以外の動画】"
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
                "",
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
                "   uploadStatus: "
                f"{video.get('uploadStatus', '')}"
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
        "【JSONにあるが、Uploadsにはない動画】"
    )
    print()


    if not json_only_ids:
        print("なし")

    else:
        for index, video_id in enumerate(
            sorted(json_only_ids),
            start=1,
        ):
            video = json_by_video_id[
                video_id
            ]

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
        "【Uploadsにあるが、JSONにはない動画】"
    )
    print()


    if not uploads_only_ids:
        print("なし")

    else:
        for index, video_id in enumerate(
            sorted(uploads_only_ids),
            start=1,
        ):
            video = current_uploads[
                video_id
            ]

            print(
                f"{index}. "
                f"{video.get('title', '')}"
            )

            print(
                f"   videoId: {video_id}"
            )

            print(
                "   URL: "
                "https://www.youtube.com/watch?v="
                f"{video_id}"
            )

            print()


    # ====================================
    # 念のための異常確認
    # ====================================

    print()
    print(
        "【videos.listにだけ存在する"
        "予期しないID】"
    )
    print()


    if not unexpected_resource_ids:
        print("なし")

    else:
        for video_id in sorted(
            unexpected_resource_ids
        ):
            print(video_id)


    # ====================================
    # 最後に重要な数字をまとめる
    # ====================================

    print()
    print("=" * 70)
    print("重要な数字のまとめ")
    print("=" * 70)

    print(
        "チャンネル画面に対応する"
        "statistics.videoCount: "
        f"{channel_info.get('videoCount')}"
    )

    print(
        f"Uploadsプレイリスト: "
        f"{len(uploads_ids)}"
    )

    print(
        f"動画本体取得成功: "
        f"{len(resource_ids)}"
    )

    print(
        f"動画本体取得失敗: "
        f"{len(missing_resource_ids)}"
    )

    print(
        "動画本体 public: "
        f"{video_privacy_counts.get('public', 0)}"
    )

    print(
        "動画本体 unlisted: "
        f"{video_privacy_counts.get('unlisted', 0)}"
    )

    print(
        "動画本体 private: "
        f"{video_privacy_counts.get('private', 0)}"
    )

    print("=" * 70)

    print(
        "診断のみ実行しました。"
    )

    print(
        "youtube.jsonへの変更・削除は"
        "行っていません。"
    )

    print("=" * 70)


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
        "INI公式YouTubeチャンネルの"
        "情報を取得しています..."
    )

    channel_info = get_channel_info()

    print(
        "statistics.videoCount: "
        f"{channel_info.get('videoCount')}"
    )


    current_uploads = (
        fetch_current_uploads(
            channel_info[
                "uploadsPlaylistId"
            ]
        )
    )

    print(
        f"Uploads取得件数: "
        f"{len(current_uploads)}件"
    )


    video_resources = (
        fetch_video_resources(
            set(
                current_uploads.keys()
            )
        )
    )


    print_diagnostics(
        json_videos,
        channel_info,
        current_uploads,
        video_resources,
    )


if __name__ == "__main__":
    main()
