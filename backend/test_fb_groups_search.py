from app.collectors.facebook_group import FacebookGroupCollector
from playwright.sync_api import sync_playwright

c = FacebookGroupCollector(headless=True)
with sync_playwright() as p:
    ctx = c.launch_browser_context(p)
    page = ctx.new_page()
    url = "https://www.facebook.com/search/posts/?q=ram"
    page.goto(url, timeout=30000, wait_until="domcontentloaded")
    page.wait_for_timeout(4000)

    # Tìm các link nhóm và link bài viết
    links = page.query_selector_all("a[href*='/groups/']")
    print("Total group links found:", len(links))
    for idx, l in enumerate(links[:6]):
        href = l.get_attribute("href") or ""
        txt = l.inner_text().strip().replace("\n", " ")
        print(f"Link {idx+1}: {href[:70]} | Text: {txt[:40]}")

    ctx.close()
