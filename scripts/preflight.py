from email.utils import parseaddr

import httpx

from margin.config import Settings

s = Settings()
with httpx.Client(timeout=20) as c:
    for name, url, key in [
        ("OpenRouter", "https://openrouter.ai/api/v1/key", s.openrouter_api_key),
        ("Firecrawl", "https://api.firecrawl.dev/v2/team/credit-usage", s.firecrawl_api_key),
        ("Resend", "https://api.resend.com/domains", s.resend_api_key),
    ]:
        try:
            r = c.get(url, headers={"Authorization": "Bearer " + key.get_secret_value()})
            if name == "Resend" and r.status_code == 401 and r.json().get("name") == "restricted_api_key":
                print("Resend: sending-only key accepted; domain read is restricted (expected).")
            else:
                print(name + ": HTTP " + str(r.status_code))
            if name == "Resend" and r.status_code == 200:
                domain = parseaddr(s.email_from)[1].split("@")[-1]
                records = r.json().get("data", [])
                print(
                    "Resend sender domain: "
                    + (
                        "test sender"
                        if domain == "resend.dev"
                        else "verified"
                        if any(d["name"] == domain and d["status"] == "verified" for d in records)
                        else "NOT VERIFIED"
                    )
                )
        except httpx.HTTPError:
            print(name + ": network check failed")
    try:
        r = c.get("https://openrouter.ai/api/v1/models")
        r.raise_for_status()
        models = [
            m
            for m in r.json()["data"]
            if m["id"].endswith(":free")
            and float(m.get("pricing", {}).get("prompt", "1")) == 0
            and float(m.get("pricing", {}).get("completion", "1")) == 0
            and "structured_outputs" in m.get("supported_parameters", [])
        ]
        print("Free structured-output model candidates:")
        for m in models[:12]:
            print(m["id"], "context=" + str(m["context_length"]))
    except (httpx.HTTPError, ValueError, KeyError):
        print("Model catalog unavailable")
