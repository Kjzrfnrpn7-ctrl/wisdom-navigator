# Audited parser used only for offline comparison

`hot_sources.py` is an unmodified copy from adsorgcn/WorkBuddy v2.3.15,
immutable commit `6efcffe70211080a18d4155c9f6739663b61a4b0`:

https://github.com/adsorgcn/WorkBuddy/blob/6efcffe70211080a18d4155c9f6739663b61a4b0/experts/ilang-wechat-awesome/skills/wechat-topic-hunter/scripts/hot_sources.py

SHA-256: `f3c247ca2cb61f14d1df09216e61c214a2f6d0f8e8d5a6121277fae3eab47501`

Copyright (c) 2026 静水流深. Distributed under the accompanying MIT license.

The candidate lab imports the pinned local file only after verifying its digest,
and only calls `parse_json` on bytes already fetched by the lab. It does not
run the upstream CLI, fetch functions, topic ranking, clustering, subscriptions,
writing, or publishing. Candidate fetching and schema validation are isolated
in the lab. Upstream absence makes only the optional comparison unavailable.
