"""Send a signed mock-provider webhook to a locally running EVE API."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import time
import urllib.request

from app.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payment-id", required=True)
    parser.add_argument("--event-id", required=True)
    parser.add_argument("--status", choices=["SUCCESS", "FAILED"], required=True)
    parser.add_argument("--url", default="http://127.0.0.1:8000/payments/webhook/")
    args = parser.parse_args()

    raw_body = json.dumps(
        {"event_id": args.event_id, "payment_id": args.payment_id, "status": args.status},
        separators=(",", ":"),
    ).encode("utf-8")
    timestamp = str(int(time.time()))
    secret = get_settings().webhook_secret.get_secret_value()
    digest = hmac.new(
        secret.encode("utf-8"), timestamp.encode("ascii") + b"." + raw_body, hashlib.sha256
    ).hexdigest()
    request = urllib.request.Request(
        args.url,
        data=raw_body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Timestamp": timestamp,
            "X-Webhook-Signature": f"sha256={digest}",
        },
    )
    with urllib.request.urlopen(request) as response:
        print(response.read().decode("utf-8"))


if __name__ == "__main__":
    main()
