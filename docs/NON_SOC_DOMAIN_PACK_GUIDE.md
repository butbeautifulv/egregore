# Non-SOC Domain Pack Guide (P11)

Goal: add a new domain/product without baking SOC semantics into `cys_core/domain/*`.

## What exists today

- **Current product assets** live under `projects/egregore/agents/` (personas, rules, plans, skills).
- **Current catalog policy defaults** are still SOC-shaped (`DEFAULT_PROFILE_ID=cybersec-soc`).
- **Master-plan migration targets** start in `cys_core/domain/catalog/product_packs.py`.

## Minimal steps to add a new domain pack

1. **Add a new profile id**
   - Create a new `ProfilePack` entry (catalog seed path) with:
     - `id`: e.g. `general`
     - `default_personas`: e.g. `["consultant"]`
     - `default_plan`: a plan id that routes to your personas

2. **Define a `ProductProfilePack`**
   - `cys_core/domain/catalog/product_packs.py`:
     - `ProductProfilePack(id=..., name=..., profiles=[...], domains=[...], personas=[...], evals=[...])`

3. **Add personas**
   - `agents/personas/<name>/agent.yaml` + `AGENT.md`
   - Add to `agents/manifest.yaml`

4. **Add routing plan**
   - `agents/plans/<plan>.yaml` and reference it from `agents/manifest.yaml`

5. **(Optional) Add eval suite smoke**
   - Use `scripts/evals/egregore_eval.py --dry-run` as a harness placeholder until you wire a real runner.

## Recommended boundaries

- Domain core models should stay generic (`RunContext`, `TraceEvent`, `EvalRun`).
- Domain-specific literals belong in product data (`agents/`, catalog seed entries) and adapters.

