import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

PHOTO_URL = "https://ini-official.com/photo/list/3"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}


def separator(title):
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def main():
    separator("INI Photo diagnostic")
    print(f"Request URL: {PHOTO_URL}")

    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        response = session.get(
            PHOTO_URL,
            timeout=30,
            allow_redirects=True,
        )
    except requests.RequestException as e:
        print("REQUEST ERROR")
        print(repr(e))
        return

    separator("1. RESPONSE INFO")

    print(f"Status code : {response.status_code}")
    print(f"Requested   : {PHOTO_URL}")
    print(f"Final URL   : {response.url}")
    print(f"Redirected  : {response.url != PHOTO_URL}")
    print(f"Encoding    : {response.encoding}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    print(f"HTML length : {len(response.text)}")

    if response.history:
        print()
        print("Redirect history:")

        for i, item in enumerate(response.history, 1):
            print(
                f"  {i}. {item.status_code} "
                f"{item.url}"
            )
            print(
                f"     Location: "
                f"{item.headers.get('Location')}"
            )
    else:
        print()
        print("Redirect history: NONE")

    soup = BeautifulSoup(response.text, "html.parser")

    separator("2. PAGE BASIC INFO")

    if soup.title:
        print("TITLE:")
        print(soup.title.get_text(" ", strip=True))
    else:
        print("TITLE: NONE")

    h1_list = [
        h.get_text(" ", strip=True)
        for h in soup.find_all("h1")
    ]

    print()
    print("H1:")
    if h1_list:
        for text in h1_list:
            print(f"  {text}")
    else:
        print("  NONE")

    separator("3. LOGIN / AUTH CHECK")

    text = soup.get_text(" ", strip=True)

    login_keywords = [
        "ログイン",
        "LOGIN",
        "Login",
        "Plus member ID",
        "Plus member",
        "会員登録",
        "新規会員登録",
        "パスワード",
    ]

    found_keywords = []

    for keyword in login_keywords:
        if keyword.lower() in text.lower():
            found_keywords.append(keyword)

    if found_keywords:
        print("Login-related keywords found:")
        for keyword in found_keywords:
            print(f"  - {keyword}")
    else:
        print("No obvious login-related keywords found.")

    separator("4. PHOTO-RELATED TEXT CHECK")

    photo_keywords = [
        "PHOTO",
        "Photo",
        "photo",
        "フォト",
    ]

    for keyword in photo_keywords:
        count = response.text.lower().count(keyword.lower())
        print(f"{keyword!r}: {count}")

    separator("5. LINKS ON PAGE")

    links = []

    for a in soup.find_all("a", href=True):
        href = urljoin(response.url, a["href"])
        label = a.get_text(" ", strip=True)

        links.append((label, href))

    print(f"Total links: {len(links)}")

    print()
    print("Photo-related links:")

    photo_links = [
        (label, href)
        for label, href in links
        if "photo" in href.lower()
        or "photo" in label.lower()
        or "フォト" in label
    ]

    if photo_links:
        for label, href in photo_links[:100]:
            print(f"  TEXT: {label!r}")
            print(f"  URL : {href}")
            print()
    else:
        print("  NONE")

    separator("6. POSSIBLE CONTENT ITEMS")

    selectors = [
        "article",
        "li",
        ".photo",
        ".photo-list",
        ".photo_list",
        ".list",
        ".item",
        ".contents",
        ".content",
        "[class*='photo']",
        "[class*='Photo']",
    ]

    for selector in selectors:
        try:
            elements = soup.select(selector)
        except Exception:
            continue

        if not elements:
            continue

        print()
        print(f"Selector: {selector}")
        print(f"Count   : {len(elements)}")

        for element in elements[:10]:
            item_text = element.get_text(
                " ",
                strip=True,
            )

            if len(item_text) > 300:
                item_text = item_text[:300] + "..."

            print(f"  {item_text!r}")

    separator("7. DATE-LIKE ELEMENTS")

    date_candidates = []

    for tag in soup.find_all(
        ["time", "p", "span", "div", "li"]
    ):
        item_text = tag.get_text(" ", strip=True)

        if not item_text:
            continue

        if (
            "2026." in item_text
            or "2025." in item_text
            or "2024." in item_text
            or "2023." in item_text
            or "2022." in item_text
            or "2021." in item_text
            or "2026/" in item_text
            or "2025/" in item_text
            or "2024/" in item_text
            or "2023/" in item_text
            or "2022/" in item_text
            or "2021/" in item_text
        ):
            if len(item_text) <= 500:
                date_candidates.append(item_text)

    # 重複を除去
    date_candidates = list(dict.fromkeys(date_candidates))

    print(f"Found: {len(date_candidates)}")

    for item in date_candidates[:50]:
        print(f"  {item!r}")

    separator("8. IMAGE CHECK")

    images = soup.find_all("img")

    print(f"Total images: {len(images)}")

    for img in images[:50]:
        src = (
            img.get("src")
            or img.get("data-src")
            or img.get("data-original")
        )

        alt = img.get("alt", "")

        if src:
            src = urljoin(response.url, src)

        print()
        print(f"  ALT: {alt!r}")
        print(f"  SRC: {src}")

    separator("9. HTML PREVIEW")

    # HTML全体を出すとActionsログが巨大になるため
    # 先頭8000文字だけ表示
    preview = response.text[:8000]

    print(preview)

    separator("10. DIAGNOSIS SUMMARY")

    print(f"Requested URL : {PHOTO_URL}")
    print(f"Final URL     : {response.url}")
    print(f"Status        : {response.status_code}")

    if response.url != PHOTO_URL:
        print()
        print(
            "RESULT: The request was redirected."
        )
        print(
            "Check the Final URL and Redirect history above."
        )

    elif found_keywords:
        print()
        print(
            "RESULT: The Photo URL itself was returned, "
            "but login/auth-related text exists."
        )
        print(
            "Check PAGE BASIC INFO, LOGIN / AUTH CHECK, "
            "and HTML PREVIEW."
        )

    else:
        print()
        print(
            "RESULT: No redirect and no obvious login "
            "keywords were detected."
        )
        print(
            "The Photo list may be accessible without "
            "authentication."
        )

    separator("END")


if __name__ == "__main__":
    main()
