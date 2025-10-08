from playwright.sync_api import sync_playwright
import requests, re, os, textwrap, json, hashlib, pathlib, subprocess

URL = os.getenv("CHECK_URL", "https://example.com")
CONSENT_SELECTOR = os.getenv("CONSENT_SELECTOR", "button#age-consent-accept")
UL_SELECTOR = os.getenv("UL_SELECTOR", "ul[style*='max-height: 400px']")
KEYWORDS = [k.strip().lower() for k in os.getenv("KEYWORDS", "available,in stock").split(",")]
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
STATE_FILE = "last_matches.json"

def notify(msg):
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ Telegram credentials missing.")
        return
    requests.get(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        params={"chat_id": CHAT_ID, "text": msg},
        timeout=10
    )

def find_keyword_context(text, keyword, context=50):
    matches = []
    for m in re.finditer(re.escape(keyword), text):
        start = max(0, m.start() - context)
        end = min(len(text), m.end() + context)
        snippet = text[start:end].replace("\n", " ")
        matches.append(snippet)
    return matches

def extract_text():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, wait_until="domcontentloaded")

        try:
            page.click(CONSENT_SELECTOR, timeout=3000)
            page.wait_for_timeout(2000)
        except Exception:
            pass

        try:
            text = page.inner_text(UL_SELECTOR).lower()
        except Exception:
            text = ""

        browser.close()
        return text

def calc_hash(data):
    """Hash a dictionary of matches for quick diffing."""
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

def run_check():
    ul_text = extract_text()
    found = {}
    for k in KEYWORDS:
        contexts = find_keyword_context(ul_text, k)
        if contexts:
            found[k] = contexts

    # load last run
    prev = {}
    if pathlib.Path(STATE_FILE).exists():
        with open(STATE_FILE, "r") as f:
            prev = json.load(f)

    # compare hashes
    old_hash, new_hash = calc_hash(prev), calc_hash(found)
    if old_hash == new_hash:
        print("🟢 No new keyword matches since last run.")
        return

    # compose message with new findings
    message_lines = [f"✅ New keyword(s) found on {URL}:"]
    for k, contexts in found.items():
        if k not in prev:
            message_lines.append(f"\n🔹 *{k}* ({len(contexts)}x NEW)")
        else:
            # only report new snippets
            new_snips = [c for c in contexts if c not in prev[k]]
            if new_snips:
                message_lines.append(f"\n🔹 *{k}* ({len(new_snips)} new)")
                for snippet in new_snips[:3]:
                    message_lines.append(f"    …{textwrap.shorten(snippet, width=120)}…")
    msg = "\n".join(message_lines)
    print(msg)
    notify(msg)

    # save new state
    with open(STATE_FILE, "w") as f:
        json.dump(found, f, indent=2)

    # commit updated state back to repo
    subprocess.run(["git", "config", "user.email", "bot@github.com"])
    subprocess.run(["git", "config", "user.name", "GitHub Action Bot"])
    subprocess.run(["git", "add", STATE_FILE])
    subprocess.run(["git", "commit", "-m", "update last_matches"] , check=False)
    subprocess.run(["git", "push"])
    print("💾 Updated last_matches.json in repository.")

if __name__ == "__main__":
    run_check()
