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
    """Return snippet(s) around keyword match."""
    matches = []
    for m in re.finditer(re.escape(keyword), text):
        start = max(0, m.start() - context)
        end = min(len(text), m.end() + context)
        snippet = text[start:end].replace("\n", " ").strip()
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
    """Hash structure to detect identical results quickly."""
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

def run_check():
    ul_text = extract_text()

    # Collect keyword + context pairs
    found_pairs = []
    for k in KEYWORDS:
        for snippet in find_keyword_context(ul_text, k):
            found_pairs.append({"keyword": k, "context": snippet})

    # Load previous matches
    prev_pairs = []
    if pathlib.Path(STATE_FILE).exists():
        with open(STATE_FILE, "r") as f:
            prev_pairs = json.load(f)

    # Build set of (keyword + snippet) for fast diff
    prev_set = {f"{x['keyword']}::{x['context']}" for x in prev_pairs}
    new_set = {f"{x['keyword']}::{x['context']}" for x in found_pairs}

    new_only = new_set - prev_set

    if not new_only:
        print("🟢 No new keyword/context combinations since last run.")
        return

    # Prepare message for Telegram
    message_lines = [f"✅ New matches found on {URL}:"]
    for entry in new_only:
        keyword, context = entry.split("::", 1)
        message_lines.append(f"\n🔹 *{keyword}*")
        message_lines.append(f"    …{textwrap.shorten(context, width=120)}…")

    msg = "\n".join(message_lines)
    print(msg)
    notify(msg)

    # Save new state (all unique seen so far)
    combined = list({e for e in prev_set | new_set})  # union
    # convert back to list of dicts
    all_pairs = [{"keyword": s.split("::", 1)[0], "context": s.split("::", 1)[1]} for s in combined]

    with open(STATE_FILE, "w") as f:
        json.dump(all_pairs, f, indent=2)

    # Commit new state back to repo
    subprocess.run(["git", "config", "user.email", "bot@github.com"])
    subprocess.run(["git", "config", "user.name", "GitHub Action Bot"])
    subprocess.run(["git", "add", STATE_FILE])
    subprocess.run(["git", "commit", "-m", "update last_matches"], check=False)
    subprocess.run(["git", "push"])
    print("💾 Updated last_matches.json in repository.")

if __name__ == "__main__":
    run_check()
