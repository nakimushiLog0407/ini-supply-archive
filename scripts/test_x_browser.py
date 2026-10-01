#!/usr/bin/env python3

"""
X 公開投稿取得・ブラウザ診断スクリプト

目的:
    Playwright + Chromium を使用して、
    GitHub Actions 上の実ブラウザ環境から
    ログインなしで公開Xプロフィールを閲覧できるか確認する。

対象:
    INI公式X
    @official__INI

重要:
    ・X公式APIは使用しない
    ・Xへのログインは行わない
    ・Cookie等の認証情報は使用しない
    ・本番JSONは変更しない
    ・GitHubへの書き込みは行わない
    ・診断結果を標準出力へ表示するだけ
"""

from __future__ import annotations

import asyncio
import re
import sys

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    async_playwright,
)


# ============================================================
# 設定
# ============================================================

USERNAME = "official__INI"

PROFILE_URL = f"https://x.com/{USERNAME}"

TIMEOUT = 30_000

WAIT_AFTER_LOAD = 8_000

MAX_POSTS_TO_PRINT = 10


# ============================================================
# 表示用
# ============================================================

def print_separator(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def shorten(text: str, limit: int = 1500) -> str:
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) <= limit:
        return text

    return text[:limit] + " ..."


# ============================================================
# ブラウザ作成
# ============================================================

async def create_browser_context(
    browser: Browser,
) -> BrowserContext:

    context = await browser.new_context(
        locale="ja-JP",
        timezone_id="Asia/Tokyo",
        viewport={
            "width": 1280,
            "height": 1600,
        },
        user_agent=(
            "Mozilla/5.0 "
            "(X11; Linux x86_64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/140.0.0.0 "
            "Safari/537.36"
        ),
    )

    return context


# ============================================================
# ページ基本情報
# ============================================================

async def print_page_information(
    page: Page,
) -> None:

    print_separator(
        "PAGE INFORMATION"
    )

    print(
        f"FINAL URL: {page.url}"
    )

    try:
        title = await page.title()
    except Exception as exc:
        title = f"(取得失敗: {exc})"

    print(
        f"TITLE: {title}"
    )

    try:
        body_text = await page.locator(
            "body"
        ).inner_text(
            timeout=10_000
        )

        print()
        print("BODY TEXT PREVIEW:")
        print(
            shorten(
                body_text,
                3000,
            )
        )

    except Exception as exc:
        print()
        print(
            f"BODY TEXT ERROR: {exc}"
        )


# ============================================================
# ログイン要求などの確認
# ============================================================

async def check_login_wall(
    page: Page,
) -> None:

    print_separator(
        "LOGIN WALL CHECK"
    )

    try:
        body_text = await page.locator(
            "body"
        ).inner_text(
            timeout=10_000
        )

    except Exception as exc:
        print(
            f"BODY TEXT ERROR: {exc}"
        )
        return

    keywords = [
        "ログイン",
        "アカウントを作成",
        "Sign in",
        "Log in",
        "Create account",
        "Something went wrong",
        "問題が発生しました",
        "Try again",
        "やりなおす",
    ]

    found_any = False

    for keyword in keywords:

        if keyword.lower() in body_text.lower():
            print(
                f"FOUND: {keyword}"
            )

            found_any = True

    if not found_any:
        print(
            "ログイン要求・エラーを示す主要キーワードは"
            "検出されませんでした。"
        )


# ============================================================
# article要素確認
# ============================================================

async def inspect_articles(
    page: Page,
) -> None:

    print_separator(
        "ARTICLE CHECK"
    )

    articles = page.locator(
        "article"
    )

    try:
        count = await articles.count()
    except Exception as exc:
        print(
            f"ARTICLE COUNT ERROR: {exc}"
        )
        return

    print(
        f"ARTICLE COUNT: {count}"
    )

    if count == 0:
        print(
            "投稿らしいarticle要素は見つかりませんでした。"
        )
        return

    limit = min(
        count,
        MAX_POSTS_TO_PRINT,
    )

    for index in range(limit):

        article = articles.nth(
            index
        )

        print()
        print(
            f"--- ARTICLE {index + 1} ---"
        )

        try:
            text = await article.inner_text(
                timeout=5_000
            )

            print(
                shorten(
                    text,
                    2000,
                )
            )

        except Exception as exc:
            print(
                f"TEXT ERROR: {exc}"
            )


# ============================================================
# 投稿URL確認
# ============================================================

async def inspect_status_links(
    page: Page,
) -> list[str]:

    print_separator(
        "STATUS LINK CHECK"
    )

    links = page.locator(
        'a[href*="/status/"]'
    )

    try:
        count = await links.count()
    except Exception as exc:
        print(
            f"STATUS LINK COUNT ERROR: {exc}"
        )
        return []

    print(
        f"STATUS LINK ELEMENTS: {count}"
    )

    urls: list[str] = []

    for index in range(count):

        link = links.nth(
            index
        )

        try:
            href = await link.get_attribute(
                "href"
            )
        except Exception:
            continue

        if not href:
            continue

        match = re.search(
            r"/([^/]+)/status/(\d+)",
            href,
        )

        if not match:
            continue

        account = match.group(1)
        status_id = match.group(2)

        if account.lower() != USERNAME.lower():
            continue

        url = (
            f"https://x.com/"
            f"{USERNAME}/status/{status_id}"
        )

        if url not in urls:
            urls.append(
                url
            )

    print(
        f"UNIQUE @{USERNAME} STATUS URLS: "
        f"{len(urls)}"
    )

    for url in urls[:30]:
        print(
            url
        )

    return urls


# ============================================================
# スクロールテスト
# ============================================================

async def scroll_page(
    page: Page,
) -> None:

    print_separator(
        "SCROLL TEST"
    )

    for index in range(3):

        print(
            f"SCROLL {index + 1}/3"
        )

        await page.mouse.wheel(
            0,
            1400,
        )

        await page.wait_for_timeout(
            2500
        )


# ============================================================
# main
# ============================================================

async def run() -> int:

    print_separator(
        "X BROWSER FETCH DIAGNOSTIC"
    )

    print(
        f"TARGET: @{USERNAME}"
    )

    print(
        "METHOD: Playwright + Chromium"
    )

    print(
        "API KEY: NOT USED"
    )

    print(
        "LOGIN: NOT USED"
    )

    print(
        "WRITE FILE: NO"
    )

    async with async_playwright() as playwright:

        print_separator(
            "START CHROMIUM"
        )

        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )

        context = await create_browser_context(
            browser
        )

        page = await context.new_page()

        try:

            print_separator(
                "OPEN PROFILE"
            )

            print(
                f"GET: {PROFILE_URL}"
            )

            response = await page.goto(
                PROFILE_URL,
                wait_until="domcontentloaded",
                timeout=TIMEOUT,
            )

            if response is None:
                print(
                    "HTTP STATUS: UNKNOWN"
                )
            else:
                print(
                    f"HTTP STATUS: "
                    f"{response.status}"
                )

            print(
                f"WAIT: {WAIT_AFTER_LOAD} ms"
            )

            await page.wait_for_timeout(
                WAIT_AFTER_LOAD
            )

            await print_page_information(
                page
            )

            await check_login_wall(
                page
            )

            await inspect_articles(
                page
            )

            first_urls = (
                await inspect_status_links(
                    page
                )
            )

            await scroll_page(
                page
            )

            print_separator(
                "AFTER SCROLL"
            )

            await inspect_articles(
                page
            )

            final_urls = (
                await inspect_status_links(
                    page
                )
            )

            combined_urls = list(
                dict.fromkeys(
                    first_urls
                    + final_urls
                )
            )

            print_separator(
                "RESULT"
            )

            print(
                f"TOTAL UNIQUE STATUS URLS: "
                f"{len(combined_urls)}"
            )

            if combined_urls:

                print()
                print(
                    "RESULT: SUCCESS CANDIDATE"
                )

                print(
                    "ログアウト状態のブラウザから"
                    "INI公式Xの投稿URLを取得できました。"
                )

                print()
                print(
                    "取得URL:"
                )

                for url in combined_urls:
                    print(
                        url
                    )

            else:

                print()
                print(
                    "RESULT: NO POSTS"
                )

                print(
                    "ログアウト状態のブラウザから"
                    "INI公式Xの投稿URLを取得できませんでした。"
                )

        except Exception as exc:

            print_separator(
                "DIAGNOSTIC ERROR"
            )

            print(
                f"{type(exc).__name__}: {exc}"
            )

        finally:

            await context.close()

            await browser.close()

    print_separator(
        "DIAGNOSTIC FINISHED"
    )

    print(
        "本番データへの書き込みは行っていません。"
    )

    return 0


def main() -> int:

    return asyncio.run(
        run()
    )


if __name__ == "__main__":
    sys.exit(
        main()
    )
