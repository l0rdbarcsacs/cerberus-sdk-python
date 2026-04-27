"""Browse the SASB Standards 2018 topic taxonomy.

Useful when mapping internal sustainability metrics to the canonical
SASB code per SICS industry — e.g. "do banks report on data security
under FN-CB-230a.1?".

Run:
    CERBERUS_API_KEY=ck_live_... python examples/sasb_topics_browse.py
"""

from __future__ import annotations

import os

from cerberus_compliance import CerberusClient


def main() -> None:
    client = CerberusClient(api_key=os.environ["CERBERUS_API_KEY"])

    # Filter by SICS industry — the slug must match exactly.  Live
    # values include "Commercial Banks", "Insurance", "Asset Management
    # & Custody Activities", "Oil & Gas — Exploration & Production",
    # etc.  Use ``client.sasb_topics.iter_all()`` if you want the full
    # ~395-row catalogue.
    page = client.sasb_topics.list(industry="Commercial Banks", limit=20)
    print(f"Commercial Banks — {page['total']} topics")
    print()
    for t in page["topics"]:
        print(f"  {t['code']:<14}  {t['topic_name']}")


if __name__ == "__main__":
    main()
