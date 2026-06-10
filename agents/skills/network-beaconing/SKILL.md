---
name: network-beaconing
description: Network beaconing, DNS anomalies, and C2 indicator analysis
---

# Network Beaconing Analysis

## When to use

- NetFlow / DNS / TLS metadata review
- Periodic callbacks to rare destinations
- East-west anomalies after endpoint alerts

## High-signal checks

1. Fixed-interval connections with low payload variance
2. Random-looking DNS labels or young TLDs
3. Traffic without corresponding user/browser activity
4. Tor/VPN exit or known-bad IP enrichment hits
5. Correlation with EDR/proxy alerts on same host

## Output guidance

Distinguish anomaly vs confirmed malicious; always cite evidence chain and confidence.
