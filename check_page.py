from playwright.sync_api import sync_playwright
import requests, re, os, textwrap

URL = os.getenv("CHECK_URL", "https://example.com")
CONSENT_SELECTOR = os.getenv("CONSENT_SELECTOR", "button#age-consent-accept")
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

def find_keyword_context(html, keyword, context=50):
    """Return snippet around found keyword."""
    matches = []
    for m in re.finditer(re.escape(keyword), html):
        start = max(0, m.start() - context)
        end = min(len(html), m.end() + context)
        snippet = html[start:end].replace("\n", " ")
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

        html = page.content().lower()
        browser.close()

        found = []
        for k in KEYWORDS:
            contexts = find_keyword_context(html, k)
            if contexts:
                found.append((k, contexts))

        if found:
            message_lines = [f"✅ Keyword(s) found on {URL}:"]
            for k, contexts in found:
                message_lines.append(f"\n🔹 *{k}* ({len(contexts)}x)")
                for snippet in contexts[:3]:  # limit to first 3 snippets per keyword
                    message_lines.append(f"    …{textwrap.shorten(snippet, width=120)}…")
            msg = "\n".join(message_lines)
            print(msg)
            # Telegram has 4096 char limit — truncate if needed
            if len(msg) > 4000:
                msg = msg[:4000] + "…"
            notify(msg)
        else:
            print("❌ No keywords found.")

if __name__ == "__main__":
    run_check()
