import json
from pathlib import Path


SOURCE_FILE = Path("data/supplies.json")
YOUTUBE_FILE = Path("data/youtube.json")


def main():
    # 現在の統合データを読み込む
    with SOURCE_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        supplies = json.load(file)

    if not isinstance(supplies, list):
        raise RuntimeError(
            "supplies.json の形式が"
            "配列ではありません。"
        )

    # YouTubeだけ抽出
    youtube_supplies = [
        supply
        for supply in supplies
        if supply.get("type") == "youtube"
    ]

    if not youtube_supplies:
        raise RuntimeError(
            "YouTubeデータが1件も"
            "見つかりませんでした。"
        )

    # youtube.jsonとして保存
    with YOUTUBE_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            youtube_supplies,
            file,
            ensure_ascii=False,
            indent=2,
        )
        file.write("\n")

    print(
        f"元データ：{len(supplies)}件"
    )

    print(
        "YouTube："
        f"{len(youtube_supplies)}件"
    )

    print(
        "data/youtube.json を"
        "作成しました。"
    )


if __name__ == "__main__":
    main()
