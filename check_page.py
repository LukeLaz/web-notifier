from playwright.sync_api import sync_playwright
import requests, re, os, textwrap

URL = os.getenv("CHECK_URL", "https://example.com")
CONSENT_SELECTOR = os.getenv("CONSENT_SELECTOR", "button#age-consent-accept")
NEWS_FEED_SELECTOR = os.getenv("NEWS_FEED_SELECTOR", "ul[style*='max-height: 400px']")  # 👈 target <ul> element
KEYWORDS = [k.strip().lower() for k in os.getenv("KEYWORDS", "available,in stock").split(",")]
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def notify(msg):
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ Telegram credentials missing.")
        return
    requests.get(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        params={"chat_id": CHAT_ID, "text": msg},
        timeout=10
    )

def find_keyword_context(text, keyword, context=100):
    """Return snippet around found keyword."""
    matches = []
    for m in re.finditer(re.escape(keyword), text):
        start = max(0, m.start() - context)
        end = min(len(text), m.end() + context)
        snippet = text[start:end].replace("\n", " ")
        matches.append(snippet)
    return matches

def run_check():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print(f"Loading {URL} …")
        page.goto(URL, wait_until="domcontentloaded")

        # Try clicking consent/age button if it exists
        try:
            page.click(CONSENT_SELECTOR, timeout=3000)
            print(f"Clicked consent selector: {CONSENT_SELECTOR}")
            page.wait_for_timeout(2000)
        except Exception as e:
            print(f"No consent element found or click failed: {e}")

        try:
            ul_text = page.inner_text(NEWS_FEED_SELECTOR).lower()
            print(f"Successfully extracted news feed (length={len(ul_text)})")
        except Exception as e:
            print(f"❌ Could not find element ({NEWS_FEED_SELECTOR}): {e}")
            ul_text = ""

        browser.close()

        found = []
        for k in KEYWORDS:
            contexts = find_keyword_context(ul_text, k)
            if contexts:
                found.append((k, contexts))

        if found:
            message_lines = [f"✅ Keyword(s) found on {URL}:"]
            for k, contexts in found:
                message_lines.append(f"\n🔹 *{k}* ({len(contexts)}x)")
                for snippet in contexts[:3]:
                    message_lines.append(f"    …{textwrap.shorten(snippet, width=120)}…")
            msg = "\n".join(message_lines)
            print(msg)
            if len(msg) > 4000:
                msg = msg[:4000] + "…"
            notify(msg)
        else:
            print("❌ No keywords found in target <ul>.")

if __name__ == "__main__":
    run_check()
