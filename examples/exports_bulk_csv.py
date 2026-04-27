"""Trigger a bulk CSV export and download the result.

Bulk exports are an enterprise-tier feature: one POST queues an async
job, ``wait()`` blocks until the worker finishes, and the response
includes a presigned URL with a 1-hour TTL that anyone can use to
download the file (including curl / wget — no Authorization header).

Run:
    CERBERUS_API_KEY=ck_live_... python examples/exports_bulk_csv.py
"""

from __future__ import annotations

import os
import urllib.request

from cerberus_compliance import CerberusClient


def main() -> None:
    client = CerberusClient(api_key=os.environ["CERBERUS_API_KEY"])

    job = client.exports.create(
        "entities",
        format="csv",
        filters={"entity_kind": "banco"},
    )
    print(f"queued: {job['export_id']}  status={job['status']}")

    ready = client.exports.wait(job["export_id"], poll_interval=2.0, timeout=120.0)
    print(
        f"ready:  rows={ready['rows_exported']:,} "
        f"bytes={ready['bytes_exported']:,} "
        f"format={ready['format']}"
    )

    # Presigned URLs are public — no Authorization header needed.
    url = ready["download_url"]
    with urllib.request.urlopen(url) as resp:
        head = resp.read(512).decode()
    print()
    print("First 512 bytes of the CSV:")
    print(head)


if __name__ == "__main__":
    main()
