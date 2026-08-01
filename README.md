# ProspectAI Scale

Prospecção automática via **Instagram Direct**: **150 DMs/dia** × **10 dias** = **1.500 leads**, com follow-ups (D1/D4/D8), Spintax, anti-ban, **CLI** e **dashboard React**.

Plano detalhado: [`project-plan.md`](./project-plan.md).

## Stack

| Camada | Tecnologia |
|--------|------------|
| API | Python 3.12+, FastAPI, SQLAlchemy, Alembic |
| Fila | Celery + Redis |
| CLI | Typer + Rich |
| Canal v1 | Instagram (`instagrapi` adapter) |
| UI | React + Vite + Tailwind + TanStack Router/Query |
| DB | SQLite (dev) / PostgreSQL (prod) |

## Pré-requisitos

- Python **3.12+**
- Node.js **20+**
- Redis (opcional — Celery worker; sem Redis use `prospectai scheduler run-due`)

## Setup rápido

### 1. Ambiente

```bash
cp .env.example .env
```

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pip install -e .
alembic upgrade head
uvicorn main:app --reload --port 8000
```

Saúde: [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)

Testes: `pytest -q` (adapter Instagram mockado — sem rede real).

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard: [http://127.0.0.1:5173](http://127.0.0.1:5173) (proxy `/api` → backend).

### 4. CLI (após backend instalado)

```bash
cd backend
source .venv/bin/activate
prospectai campaign create --name "Campanha Q3"
prospectai import ../examples/leads_1500.csv --campaign "Campanha Q3" --confirm
prospectai campaign start <id>
prospectai accounts add --username minha_conta
prospectai accounts login <account-uuid> --password '...'   # ou prompt seguro
prospectai accounts inbox-poll [--account UUID]
prospectai scheduler run-due          # processa jobs vencidos (sem Redis)
prospectai scheduler list --campaign <id>
# ou: PYTHONPATH=. python -m cli --help
```

### 5. Instagram adapter (`INSTAGRAM_ADAPTER`)

| Valor | Uso |
|-------|-----|
| `stub` (default) | Testes/CI — sem rede; `send_dm` simula sucesso |
| `instagrapi` | Login/DM/inbox reais via [instagrapi](https://github.com/subzeroid/instagrapi) |

```bash
# .env
INSTAGRAM_ADAPTER=instagrapi
# SESSIONS_DIR=./backend/data/sessions   # sessões JSON — nunca commitar
```

**Riscos:** automação via API privada viola ToS do Instagram e pode gerar ban, challenge/checkpoint ou rate limit. Use contas de warm-up, proxies estáveis e os limites do anti-ban (F4).

**2FA / challenge:** se o Instagram pedir verificação, o status da conta fica `challenge` — resolva no app oficial e faça login de novo. 2FA TOTP não é automatizado na F3 (passe código manualmente se o fluxo do instagrapi pedir).

Login real (manual):

```bash
export INSTAGRAM_ADAPTER=instagrapi
prospectai accounts add --username SEU_USER
prospectai accounts login <id>   # prompt de senha; grava sessão em sessions_dir
```

### 6. Worker Celery (opcional — precisa Redis)

```bash
cd backend && source .venv/bin/activate
celery -A celery_app.celery worker -l info
celery -A celery_app.celery beat -l info    # process_due 60s + inbox 5 min
```

Sem Redis, use `prospectai scheduler run-due` / `prospectai accounts inbox-poll` em loop/cron.

## Dados de exemplo

- [`examples/leads_1500.csv`](./examples/leads_1500.csv) — 1.500 leads fictícios (`nome`, `empresa`, `cargo`, `instagram`, `cidade`, `observacoes`)

## Escalando com múltiplas contas Instagram

Para ~150 DMs/dia com segurança, use **3–5 contas** com warm-up:

| Contas | DMs/conta/dia | Total |
|--------|---------------|-------|
| 3 | ~50 | 150 |
| 5 | ~30 | 150 |

Configure contas pelo dashboard **Contas** ou pela CLI. Proxies opcionais via `PROXY_URLS` no `.env`.

## Estrutura

```
backend/     # FastAPI, services, adapters, CLI
frontend/    # React SPA
examples/    # CSV de leads
docs/        # Documentação adicional
.cursor/     # Regras e agentes Cursor
```

## Docker

Opcional — só quando pedido / fase de polish. Não é necessário para desenvolvimento local.

## Status

| Fase | Estado |
|------|--------|
| **F1 — Core** | ✅ Models, API, importador, CLI, dashboard shell |
| **F2 — Scheduler** | ✅ Slots 150/dia, follow-ups D+3/D+7, pause/resume, worker Celery/CLI |
| **F3 — Instagram** | ✅ Adapter `instagrapi` + stub, login, inbox poll |
| **F4 — Anti-ban** | ✅ Rate limit, warm-up, circuit breaker, auto-pause |
| **F5 — Templates** | ✅ Variáveis + Spintax + preview API/UI |
| **F6 — Dashboard** | ✅ Ações campanha, jobs, contas, import leads, polling |
| **F7 — Polish** | ⬜ Docker opcional / docs finais |
