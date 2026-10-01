"""
Checks whether the Roadie Jira plugin will show data for a Backstage component.

HARDCODED FOR LOCAL TESTING ONLY: fill in the values below, then run:
    python test_jira_setup.py
Do NOT commit this file or share it while it contains your token.
No third-party packages required.
"""
import base64
import json
import re
import sys
import urllib.error
import urllib.request

# ----------------------- EDIT THESE VALUES -----------------------
JIRA_BASE_URL = "https://devtools-team-bwt0w9xy.atlassian.net"   # no trailing slash
JIRA_EMAIL = "yashwanthv@devtools.in"
JIRA_API_TOKEN = "ATATT3xFfGF0sQYmv7Fs398lWXsgOuWY4Bs1COUjRzmyusHhJzgCgpt2L7vgQQwoaQF7DmWQmGg6ZmU8OA1VRy4YDRotTeU-SravP1sa-7UoMc87ZMvEq2ilCR5S53ie8JxV3fxnuztHQIUVMoTfFk4W0W4WAhgO50ZBbYaxCimSOWx8MNpXM0Q=3814AC6A"               # raw API token, not base64
CATALOG_INFO_PATH = r"C:\Users\YashwanthVenkatesh\Desktop\python-app\catalog-info.yaml"   # your component file
# -----------------------------------------------------------------

_basic = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode("utf-8")).decode()
JIRA_TOKEN = f"Basic {_basic}"  # same format Backstage's proxy uses

OK, BAD, WARN = "[PASS]", "[FAIL]", "[WARN]"


def read_annotations(path):
    """Very small parser: collects key: value lines under 'annotations:'."""
    annotations, in_block, indent = {}, False, 0
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if line.strip().startswith("#") or not line.strip():
                continue
            if re.match(r"^\s*annotations:\s*$", line):
                in_block, indent = True, len(line) - len(line.lstrip())
                continue
            if in_block:
                cur = len(line) - len(line.lstrip())
                if cur <= indent:
                    in_block = False
                    continue
                m = re.match(r"^\s*([^:\s]+):\s*(.*)$", line)
                if m:
                    annotations[m.group(1)] = m.group(2).strip().strip("'\"")
    return annotations


def http_get(url, headers):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # network / DNS / refused
        return None, str(e)


def main():
    if "PASTE_NEW_TOKEN_HERE" in JIRA_API_TOKEN or "YOURCOMPANY" in JIRA_BASE_URL:
        print("Edit the values at the top of this file first.")
        sys.exit(1)

    failures = 0

    # 1. Annotation check
    ann = read_annotations(CATALOG_INFO_PATH)
    key = ann.get("jira/project-key")
    if key:
        print(f"{OK} Found Roadie annotation jira/project-key = {key}")
    else:
        failures += 1
        print(f"{BAD} Annotation 'jira/project-key' not found.")
        if "jira.com/project-key" in ann:
            print("       You have 'jira.com/project-key' - that is the AXIS plugin's")
            print("       format. Roadie needs:  jira/project-key: " + ann["jira.com/project-key"])
        sys.exit(1)

    # 2. Environment check
    base = JIRA_BASE_URL.rstrip("/")
    print(f"{OK} Using Jira URL {base} and user {JIRA_EMAIL}")

    headers = {
        "Authorization": JIRA_TOKEN,
        "Accept": "application/json",
        "X-Atlassian-Token": "nocheck",
        "User-Agent": "Backstage-Jira-Plugin",
    }

    # 3. Auth + project exists
    status, body = http_get(f"{base}/rest/api/3/project/{key}", headers)
    if status == 200:
        proj = json.loads(body)
        print(f"{OK} Jira project found: {proj.get('name')} ({proj.get('key')})")
    elif status in (401, 403):
        failures += 1
        print(f"{BAD} Jira returned {status}: bad token/email, or no Browse Projects permission")
    elif status == 404:
        failures += 1
        print(f"{BAD} Project '{key}' not found, or this user cannot see it")
    else:
        failures += 1
        print(f"{BAD} Could not reach Jira (status={status}): {body[:200]}")

    # 4. Issues are readable
    if status == 200:
        jql = urllib.request.quote(f"project = {key}")
        s2, b2 = http_get(f"{base}/rest/api/3/search/jql?jql={jql}&maxResults=3&fields=summary,status", headers)
        if s2 == 200:
            issues = json.loads(b2).get("issues", [])
            print(f"{OK} Issue search works ({len(issues)} sample issue(s) returned)")
            for i in issues:
                print(f"       {i['key']}: {i['fields'].get('summary')}")
            if not issues:
                print(f"{WARN} Project has no issues - the card will show zero counts")
        else:
            failures += 1
            print(f"{BAD} Issue search failed (status={s2}): {b2[:200]}")

    # 5. Optional: through the Backstage proxy (needs `yarn dev` running)
    proxy_url = f"http://localhost:7007/api/proxy/jira/api/rest/api/3/project/{key}"
    s3, b3 = http_get(proxy_url, {"Accept": "application/json"})
    if s3 == 200:
        print(f"{OK} Backstage proxy /jira/api works")
    elif s3 in (401, 403):
        print(f"{WARN} Proxy returned {s3}. Backstage may require login for the proxy;")
        print("       this is not necessarily a problem when the browser is signed in.")
    elif s3 is None:
        print(f"{WARN} Backstage not reachable on localhost:7007 (is 'yarn dev' running?)")
    else:
        failures += 1
        print(f"{BAD} Proxy returned {s3}. Check proxy.endpoints['/jira/api'] in app-config.yaml")

    print()
    if failures:
        print(f"{failures} check(s) failed - fix those before expecting the Jira card.")
        sys.exit(1)
    print("Jira side looks good. If the card is still missing, the issue is in the")
    print("frontend wiring (App.tsx / modules/jira.tsx) or the entity isn't re-registered.")


if __name__ == "__main__":
    main()