# Installation Guide (Linux + Windows)

## Requirements
- Python 3.12+
- pip
- Git

## Linux (bash)
```bash
git clone <your-public-repo-url>
cd vk-openclaw-service
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install ruff mypy bandit pip-audit pytest
cp .env.example .env
```

Run service:
```bash
uvicorn vk_openclaw_service.main:app --reload
```

Run worker:
```bash
vk-openclaw-worker --once
```

## Windows PowerShell
```powershell
git clone <your-public-repo-url>
cd vk-openclaw-service
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install ruff mypy bandit pip-audit pytest
Copy-Item .env.example .env
```

Run service:
```powershell
uvicorn vk_openclaw_service.main:app --reload
```

Run worker:
```powershell
vk-openclaw-worker --once
```

## Windows CMD
```cmd
git clone <your-public-repo-url>
cd vk-openclaw-service
py -3.12 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install ruff mypy bandit pip-audit pytest
copy .env.example .env
```

Run service:
```cmd
uvicorn vk_openclaw_service.main:app --reload
```

Run worker:
```cmd
vk-openclaw-worker --once
```

## Required runtime variables
Set real values in local `.env` only:
- `ADMIN_API_TOKEN`
- `VK_ACCESS_TOKEN`
- `VK_ALLOWED_PEERS`
- `OPENCLAW_COMMAND`

VK token/peer setup details:
- `docs/vk_setup.md`

## Verification
Linux/macOS:
```bash
pytest tests/unit
```

Windows PowerShell:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_pytest_safe.ps1 -q
```

## Interactive installer (WSL)
`vk-openclaw install` now asks for required values during setup:
- `ADMIN_API_TOKEN` (auto-generate on Enter)
- `VK_ACCESS_TOKEN`
- `VK_ALLOWED_PEERS` (peer_id)
- `PERSISTENCE_MODE` (+ `DATABASE_DSN` and `REDIS_DSN` for `database` mode)
- `OPENCLAW_COMMAND`

The installer shows short hints for each critical field and writes secrets to `.env.local`.
