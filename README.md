# cerberus-compliance

Official Python SDK for the **Cerberus Compliance API** (Chile RegTech).

> Status: `v0.1.0-rc1` — foundation only. Full resource coverage shipped by Instances B/C/D in feat/resources-1, feat/resources-2, feat/dx-examples.

## Install

```bash
pip install cerberus-compliance
```

## Quickstart

```python
from cerberus_compliance import CerberusClient

client = CerberusClient(api_key="ck_live_...")  # or env CERBERUS_API_KEY

# Sub-resources are wired by Instances B/C — see CHANGELOG once published.
```

See `docs/HANDOFF_A.md` for the foundation handoff and the parallel-instance contract.

## License

MIT — see [LICENSE](./LICENSE).
