import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://ini-official.com"
LIST_URL = "https://ini-official.com/photo/list/3"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    )
}


def print_section(title):
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def get_html(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    return response


def print_attributes(tag):
    """タグの属性を見やすく表示する"""
    if not tag:
        return

    for key, value in tag.attrs.items():
        print(f"  {key}: {value}")


def main():
    print_section("INI Photo thumbnail diagnostic")

    # ------------------------------------------------------------
    # 1. Photo一覧ページ取得
    # ------------------------------------------------------------

    print_section("1. GET PHOTO LIST PAGE")

    response = get_html(LIST_URL)

    print(f"Status code : {response.status_code}")
    print(f"Final URL   : {response.url}")
    print(f"HTML length : {len(response.text)}")

    soup = BeautifulSoup(response.text, "html.parser")

    # ------------------------------------------------------------
    # 2. Photo個別ページへのリンクを取得
    # ------------------------------------------------------------

    print_section("2. PHOTO DETAIL LINKS")

    detail_links = []

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")

        if re.search(r"/photo/\d+/detail/\d+", href):
            full_url = urljoin(BASE_URL, href)

            if full_url not in detail_links:
                detail_links.append(full_url)

                print()
                print(f"TEXT: {a.get_text(' ', strip=True)!r}")
                print(f"URL : {full_url}")

    print()
    print(f"Detail link count: {len(detail_links)}")

    if not detail_links:
        print("ERROR: Photo detail links were not found.")
        return

    # 最新Photoを診断対象にする
    target_url = detail_links[0]

    print()
    print(f"TARGET: {target_url}")

    # ------------------------------------------------------------
    # 3. 一覧ページ上で最新Photoを含むリンク周辺を調査
    # ------------------------------------------------------------

    print_section("3. TARGET LINK HTML ON LIST PAGE")

    target_link = None

    for a in soup.find_all("a", href=True):
        full_url = urljoin(BASE_URL, a.get("href", ""))

        if full_url == target_url:
            target_link = a
            break

    if target_link:
        print(target_link.prettify())

        print()
        print("--- LINK ATTRIBUTES ---")
        print_attributes(target_link)

        print()
        print("--- PARENT HTML ---")

        parent = target_link.parent

        if parent:
            print(parent.prettify())

        print()
        print("--- GRANDPARENT HTML ---")

        grandparent = parent.parent if parent else None

        if grandparent:
            print(grandparent.prettify())

    else:
        print("Target link element was not found.")

    # ------------------------------------------------------------
    # 4. 最新Photo周辺にある画像を確認
    # ------------------------------------------------------------

    print_section("4. IMAGES AROUND TARGET")

    search_root = target_link

    # 親を数段上がってPhotoカード全体らしき範囲を見る
    for _ in range(4):
        if search_root and search_root.parent:
            search_root = search_root.parent

    if search_root:
        images = search_root.find_all("img")

        print(f"Image count around target: {len(images)}")

        for i, img in enumerate(images, 1):
            print()
            print(f"[IMAGE {i}]")
            print_attributes(img)

            src = img.get("src")
            if src:
                print(f"  resolved src: {urljoin(BASE_URL, src)}")

            for attr in [
                "data-src",
                "data-original",
                "data-lazy",
                "data-lazy-src",
                "data-image",
                "srcset",
            ]:
                value = img.get(attr)

                if value:
                    print(f"  {attr}: {value}")

    # ------------------------------------------------------------
    # 5. style属性からbackground-imageを探す
    # ------------------------------------------------------------

    print_section("5. BACKGROUND IMAGE CHECK")

    style_elements = soup.find_all(style=True)

    background_candidates = []

    for tag in style_elements:
        style = tag.get("style", "")

        if (
            "background" in style.lower()
            or ".jpg" in style.lower()
            or ".jpeg" in style.lower()
            or ".png" in style.lower()
            or ".webp" in style.lower()
        ):
            background_candidates.append(tag)

    print(f"Candidates: {len(background_candidates)}")

    for i, tag in enumerate(background_candidates[:100], 1):
        print()
        print(f"[CANDIDATE {i}]")
        print(f"TAG   : {tag.name}")
        print(f"CLASS : {tag.get('class')}")
        print(f"STYLE : {tag.get('style')}")

        text = tag.get_text(" ", strip=True)

        if text:
            print(f"TEXT  : {text[:300]!r}")

    # ------------------------------------------------------------
    # 6. data-* 属性を総当たり確認
    # ------------------------------------------------------------

    print_section("6. DATA ATTRIBUTE CHECK")

    data_candidates = []

    for tag in soup.find_all(True):
        data_attrs = {
            key: value
            for key, value in tag.attrs.items()
            if key.startswith("data-")
        }

        if data_attrs:
            data_candidates.append((tag, data_attrs))

    print(f"Elements with data-* attributes: {len(data_candidates)}")

    for i, (tag, attrs) in enumerate(data_candidates[:100], 1):
        print()
        print(f"[DATA {i}]")
        print(f"TAG   : {tag.name}")
        print(f"CLASS : {tag.get('class')}")

        for key, value in attrs.items():
            print(f"{key}: {value}")

    # ------------------------------------------------------------
    # 7. HTML全体から画像URLらしきものを抽出
    # ------------------------------------------------------------

    print_section("7. IMAGE URL SEARCH IN RAW HTML")

    image_pattern = re.compile(
        r"""(?:"|')([^"']+\.(?:jpg|jpeg|png|webp|gif)(?:\?[^"']*)?)(?:"|')""",
        re.IGNORECASE,
    )

    image_urls = []

    for match in image_pattern.findall(response.text):
        full_url = urljoin(BASE_URL, match)

        if full_url not in image_urls:
            image_urls.append(full_url)

    print(f"Image-like URLs found: {len(image_urls)}")

    for url in image_urls:
        print(url)

    # ------------------------------------------------------------
    # 8. 個別Photoページを取得
    # ------------------------------------------------------------

    print_section("8. GET TARGET DETAIL PAGE")

    detail_response = get_html(target_url)

    print(f"Status code : {detail_response.status_code}")
    print(f"Final URL   : {detail_response.url}")
    print(f"HTML length : {len(detail_response.text)}")

    detail_soup = BeautifulSoup(
        detail_response.text,
        "html.parser",
    )

    if detail_soup.title:
        print(f"TITLE       : {detail_soup.title.get_text(strip=True)}")

    # ------------------------------------------------------------
    # 9. 個別ページの画像
    # ------------------------------------------------------------

    print_section("9. DETAIL PAGE IMAGES")

    detail_images = detail_soup.find_all("img")

    print(f"Total images: {len(detail_images)}")

    for i, img in enumerate(detail_images, 1):
        print()
        print(f"[IMAGE {i}]")

        alt = img.get("alt")
        src = img.get("src")

        print(f"ALT: {alt!r}")
        print(f"SRC: {src!r}")

        if src:
            print(f"RESOLVED: {urljoin(BASE_URL, src)}")

        for attr in [
            "data-src",
            "data-original",
            "data-lazy",
            "data-lazy-src",
            "data-image",
            "srcset",
        ]:
            value = img.get(attr)

            if value:
                print(f"{attr}: {value}")

    # ------------------------------------------------------------
    # 10. 個別ページのbackground-image
    # ------------------------------------------------------------

    print_section("10. DETAIL PAGE BACKGROUND IMAGE CHECK")

    detail_style_elements = detail_soup.find_all(style=True)

    count = 0

    for tag in detail_style_elements:
        style = tag.get("style", "")

        if (
            "background" in style.lower()
            or ".jpg" in style.lower()
            or ".jpeg" in style.lower()
            or ".png" in style.lower()
            or ".webp" in style.lower()
        ):
            count += 1

            print()
            print(f"[CANDIDATE {count}]")
            print(f"TAG   : {tag.name}")
            print(f"CLASS : {tag.get('class')}")
            print(f"STYLE : {style}")

    print()
    print(f"Background candidates: {count}")

    # ------------------------------------------------------------
    # 11. 個別ページHTMLから画像URLを直接探索
    # ------------------------------------------------------------

    print_section("11. DETAIL RAW HTML IMAGE URL SEARCH")

    detail_image_urls = []

    for match in image_pattern.findall(detail_response.text):
        full_url = urljoin(BASE_URL, match)

        if full_url not in detail_image_urls:
            detail_image_urls.append(full_url)

    print(f"Image-like URLs found: {len(detail_image_urls)}")

    for url in detail_image_urls:
        print(url)

    print_section("END")


if __name__ == "__main__":
    main()
