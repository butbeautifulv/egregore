---
name: ci-cd-threats
description: CI/CD and supply-chain threat patterns for authorized repo assessment
---

# CI/CD Threat Patterns

## When to use

- GitHub Actions / GitLab CI workflow review
- `pull_request_target` and fork-based attacks
- Secrets in workflow env or logs
- Third-party action pinning and supply chain

## High-signal checks

1. Workflows triggered by `pull_request_target` from forks with checkout of untrusted code
2. Secrets available to workflows from fork PRs
3. Unpinned third-party actions (`@main`, floating tags)
4. Self-hosted runners with excessive permissions
5. OIDC trust policies that are too broad

## Output guidance

Correlate weak signals into exploit paths; state preconditions and blast radius.
