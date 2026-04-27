"""Inspect the calling API key's metadata.

Useful at app boot to log which tier/scopes/quota the key currently has,
so misconfigurations surface immediately instead of as 403s in
production traffic.

Run:
    CERBERUS_API_KEY=ck_live_... python examples/admin_api_keys_introspect.py
"""

from __future__ import annotations

import os

from cerberus_compliance import CerberusClient


def main() -> None:
    client = CerberusClient(api_key=os.environ["CERBERUS_API_KEY"])
    info = client.admin_api_keys.me()

    print(f"key_prefix:   {info['key_prefix']}")
    print(f"env:          {info['env']}")
    print(f"tier:         {info['tier']}")
    print(f"scopes:       {len(info['scopes'])} ({', '.join(info['scopes'][:4])}, ...)")
    print(f"expires_at:   {info.get('expires_at') or 'never'}")
    print(f"last_used_at: {info.get('last_used_at') or 'never'}")

    q = info.get("quota") or {}
    if q.get("monthly_limit") == -1:
        print("monthly:      unlimited (enterprise)")
    else:
        print(
            f"monthly:      {q['monthly_consumed']:,} / {q['monthly_limit']:,} "
            f"({q['monthly_remaining']:,} remaining; resets {q['period_end']})"
        )

    daily = info.get("daily_quota") or {}
    if daily.get("daily_limit") == -1:
        print("daily:        unlimited")
    elif daily:
        print(
            f"daily:        {daily['daily_consumed']:,} / {daily['daily_limit']:,} "
            f"(resets {daily['period_end']})"
        )


if __name__ == "__main__":
    main()
