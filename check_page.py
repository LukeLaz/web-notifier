from playwright.sync_api import sync_playwright
import requests, re, os

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

        if any(re.search(k, html) for k in KEYWORDS):
            msg = f"✅ Keyword found on {URL}"
            print(msg)
            notify(msg)
        else:
            print("❌ No keywords found.")

if __name__ == "__main__":
    run_check()
