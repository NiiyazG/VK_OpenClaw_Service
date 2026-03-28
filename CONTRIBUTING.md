# Contributing

## Local Setup
```bash
python -m pip install -e .
python -m pip install ruff mypy bandit pip-audit pytest
```

## Verification
Use the repo-local helpers instead of ad hoc command sequences:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify_release.ps1 -q
```

This runs:
- full `pytest` through `scripts/run_pytest_safe.ps1`
- `compileall`
- `ruff`
- `mypy`
- `bandit`
- wheel build through `scripts/build_package_safe.ps1`
- source distribution build through `scripts/build_sdist_safe.ps1`
- wheel metadata and entrypoint validation through `scripts/verify_artifact.py`
- source distribution contents validation through `scripts/verify_sdist.py`
- source distribution rebuild smoke through `scripts/verify_sdist_rebuild.py`
- wheel extract/import smoke through `scripts/verify_install_smoke.py`
- release handoff bundle creation through `scripts/build_release_bundle.py`
- release handoff bundle verification through `scripts/verify_release_bundle.py`
- release manifest sync through `scripts/generate_release_manifest.py`
- release manifest verification through `scripts/verify_release_manifest.py`
- optional `pip-audit` when `RUN_PIP_AUDIT=1` is set

It also refreshes:
- `.verify_reports/release_summary.json`
- `.verify_reports/release_summary.md`
- `.verify_reports/distribution_checksums.txt`
- `.verify_reports/release_manifest.json`
- `.verify_reports/release_manifest.md`
- `.release_bundle/`

The final summary and manifest now stay step-for-step aligned, including `release-manifest` and `release-manifest-artifact`.

CI runs the same gate with `RUN_PIP_AUDIT=1`, publishes the markdown summary into the job summary, uploads `.verify_reports/*` as `verification-reports`, uploads `.dist_verify/*` as `distribution-artifacts`, and uploads `.release_bundle/*` as `release-handoff-bundle`.

To verify that a distributable wheel can be produced in sandboxed Windows environments:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_package_safe.ps1
```

For the online dependency audit in a network-enabled environment:

```powershell
$env:RUN_PIP_AUDIT = "1"
powershell -ExecutionPolicy Bypass -File scripts/verify_release.ps1 -q
```

## Expectations
- Keep `README.md`, `docs/progress.md`, and `docs/context_summary.md` aligned with the current implementation state.
- Preserve the verified admin/runtime surface unless the change explicitly evolves the API contract.
- Prefer updating or extending tests alongside any runtime change.

## Current Baseline
- Full suite: `205 passed`
- Static checks: `compileall`, `ruff`, `mypy`, `bandit`, `pip-audit` passing
- Packaging check: local wheel build passing
- Source distribution check: local sdist build passing
- Source rebuild smoke: wheel-from-sdist passing
- Install smoke: wheel extract/import passing
- External verification gap: none

## Platform Install Commands

Detailed commands for Linux, Windows PowerShell, and Windows CMD are in:
- `docs/install.md`

## VK Access Data

How to get VK token and peer identifiers:
- `docs/vk_setup.md`

## Maintainer
- Гарипов Нияз Варисович
- garipovn@yandex.ru
