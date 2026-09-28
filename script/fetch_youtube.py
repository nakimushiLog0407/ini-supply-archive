import json
import os
import urllib.parse
import urllib.request
from pathlib import Path


# ========================================
# 基本設定
# ========================================

API_KEY = os.environ.get("YOUTUBE_API_KEY")

# INI公式YouTubeチャンネル
CHANNEL_ID = "UCc-itdQHxLvUlPrDxIiSJrA"

# 初回取得の開始日
START_DATE = "2021-01-01T00:00:00Z"

# データ保存先
OUTPUT_FILE = Path("data/supplies.json")


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
# 既存データを読み込む
# ========================================

def load_existing_supplies():
    if not OUTPUT_FILE.exists():
        return []

    with OUTPUT_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


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
# APIデータを供給データへ変換
# ========================================

def make_supply(item):
    snippet = item.get("snippet", {})

    video_id = (
        item
        .get("contentDetails", {})
        .get("videoId")
    )

    published_at = snippet.get("publishedAt")
    title = snippet.get("title", "")

    if not video_id or not published_at:
        return None

    # 削除・非公開動画は登録しない
    if title in (
        "Deleted video",
        "Private video",
    ):
        return None

    return {
        "id": f"youtube-{video_id}",
        "type": "youtube",
        "date": published_at[:10],
        "title": title,
        "videoId": video_id,
    }


# ========================================
# 初回取得
# 2021年～現在まで取得
# ========================================

def fetch_initial_videos(uploads_playlist_id):
    print(
        "初回取得：2021年以降の動画を取得します。"
    )

    videos = []
    page_token = None

    while True:
        params = {
            "part": "snippet,contentDetails",
            "playlistId": uploads_playlist_id,
            "maxResults": 50,
        }

        if page_token:
            params["pageToken"] = page_token

        data = youtube_api(
            "playlistItems",
            params,
        )

        reached_start_date = False

        for item in data.get("items", []):
            published_at = (
                item
                .get("snippet", {})
                .get("publishedAt")
            )

            if not published_at:
                continue

            # 2021年より前まで来たら終了
            if published_at < START_DATE:
                reached_start_date = True
                break

            supply = make_supply(item)

            if supply:
                videos.append(supply)

        if reached_start_date:
            break

        page_token = data.get(
            "nextPageToken"
        )

        if not page_token:
            break

    return videos


# ========================================
# 2回目以降：差分取得
# ========================================

def fetch_new_videos(
    uploads_playlist_id,
    known_video_ids,
):
    print(
        "差分取得：新しい動画を確認します。"
    )

    new_videos = []
    page_token = None

    while True:
        params = {
            "part": "snippet,contentDetails",
            "playlistId": uploads_playlist_id,
            "maxResults": 50,
        }

        if page_token:
            params["pageToken"] = page_token

        data = youtube_api(
            "playlistItems",
            params,
        )

        reached_known_video = False

        for item in data.get("items", []):
            supply = make_supply(item)

            if not supply:
                continue

            video_id = supply["videoId"]

            # 保存済みの動画まで来たら、
            # それより古い動画の確認は不要
            if video_id in known_video_ids:
                reached_known_video = True
                break

            new_videos.append(supply)

        if reached_known_video:
            break

        page_token = data.get(
            "nextPageToken"
        )

        if not page_token:
            break

    return new_videos


# ========================================
# データを保存
# ========================================

def save_supplies(supplies):
    # IDを使って重複を除外
    unique_supplies = {}

    for supply in supplies:
        supply_id = supply.get("id")

        if not supply_id:
            continue

        unique_supplies[supply_id] = supply

    result = list(
        unique_supplies.values()
    )

    # 日付 → ID の順に並べる
    result.sort(
        key=lambda item: (
            item.get("date", ""),
            item.get("id", ""),
        )
    )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            result,
            file,
            ensure_ascii=False,
            indent=2,
        )

        file.write("\n")


# ========================================
# メイン処理
# ========================================

def main():
    if not API_KEY:
        raise RuntimeError(
            "YOUTUBE_API_KEY が設定されていません。"
        )

    existing_supplies = (
        load_existing_supplies()
    )

    # 既存のYouTube供給を抽出
    existing_youtube = [
        supply
        for supply in existing_supplies
        if supply.get("type") == "youtube"
        and supply.get("videoId")
    ]

    # 登録済みvideoId
    known_video_ids = {
        supply["videoId"]
        for supply in existing_youtube
    }

    print(
        f"既存のYouTube動画："
        f"{len(known_video_ids)}件"
    )

    print(
        "INI公式YouTubeチャンネルを確認します..."
    )

    uploads_playlist_id = (
        get_uploads_playlist_id()
    )

    # ====================================
    # 初回
    # ====================================

    if not known_video_ids:
        youtube_supplies = (
            fetch_initial_videos(
                uploads_playlist_id
            )
        )

        final_supplies = (
            existing_supplies
            + youtube_supplies
        )

        save_supplies(final_supplies)

        print(
            f"初回取得完了："
            f"{len(youtube_supplies)}件"
        )

        return

    # ====================================
    # 2回目以降
    # ====================================

    new_videos = fetch_new_videos(
        uploads_playlist_id,
        known_video_ids,
    )

    if not new_videos:
        print(
            "新しいYouTube動画はありません。"
        )

        return

    final_supplies = (
        existing_supplies
        + new_videos
    )

    save_supplies(final_supplies)

    print(
        f"新規動画：{len(new_videos)}件"
    )

    print(
        "supplies.jsonを更新しました。"
    )


if __name__ == "__main__":
    main()
