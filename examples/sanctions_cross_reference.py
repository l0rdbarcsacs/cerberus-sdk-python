"""Cross-reference a person against OFAC SDN, UN Consolidated, and CMF lists.

Demonstrates the AML pre-screening flow: take a candidate name and/or
RUT, hit the unified cross-reference endpoint, and print the top
matches with their issuing programme and confidence score.

Run:
    CERBERUS_API_KEY=ck_live_... python examples/sanctions_cross_reference.py
"""

from __future__ import annotations

import os

from cerberus_compliance import CerberusClient


def main() -> None:
    client = CerberusClient(api_key=os.environ["CERBERUS_API_KEY"])

    # Full names yield much higher Jaro-Winkler scores than partial.
    # Two-name "Putin" matches very poorly against "PUTIN, Vladimir
    # Vladimirovich" (~0.55); the full triple-name form scores 0.99+.
    result = client.sanctions.cross_reference(
        name="PUTIN Vladimir Vladimirovich",
        threshold=0.92,
        limit=10,
    )

    print(
        f"Query: name={result['query']['name']!r} "
        f"rut={result['query']['rut'] or '-'} "
        f"threshold={result['threshold']}"
    )
    print(f"Total matches: {result['total']}")
    print()

    for match in result["matches"][:5]:
        programs = ", ".join(match.get("programs") or [])
        print(
            f"  [{match['source']:16s}] {match['name']!r:50s} "
            f"score={match['score']:.4f}  programs=[{programs}]"
        )


if __name__ == "__main__":
    main()
