# ProspectAI Scale — Plano do Projeto

## Visão geral

Ferramenta completa de **prospecção automática via Instagram Direct** que envia mensagens personalizadas para **150 leads por dia**, durante **10 dias consecutivos** (total de **1.500 leads**), com follow-ups, anti-ban e dashboard de controle.

### Decisões definidas (v1)

| Decisão | Escolha |
|---------|---------|
| **Canal principal** | **Instagram Direct** |
| **Interface** | **CLI + Dashboard React** |

Canais adicionais (Email, WhatsApp, LinkedIn) ficam como extensão pós-v1 via adapters.

---

## 1. Objetivo e escopo

| Item | Especificação |
|------|---------------|
| Volume diário | Exatamente **150 mensagens/dia** |
| Duração | **10 dias consecutivos** sem intervenção manual |
| Total de leads | **1.500** por campanha |
| Janela de envio | Horário útil configurável (padrão **09h–18h**) |
| Follow-ups | Até **3 etapas** por lead (Dia 1, Dia 4, Dia 8) |
| Canal v1 | **Instagram Direct** (multi-contas com rotação) |
| Interface v1 | **CLI (Typer)** + **Dashboard React** |

### Fora do escopo (v1)

- Resposta automática a replies (apenas cancelamento de follow-up se houver resposta)
- CRM completo / pipeline de vendas
- Multi-tenant SaaS (estrutura preparada para escalar, mas v1 single-user)
- Canais Email, WhatsApp e LinkedIn (adapters futuros)

---

## 2. Requisitos obrigatórios

### 2.1 Volume e ritmo

- [ ] Enviar **exatamente 150 mensagens por dia** (configurável, default 150)
- [ ] Distribuir envios uniformemente ao longo do dia útil (09h–18h)
- [ ] Intervalo **inteligente e aleatório** entre mensagens (**mín. 2–5 min**, configurável)
- [ ] Capacidade de rodar **10 dias seguidos** sem intervenção manual
- [ ] Pausa automática fora do horário; retoma no próximo slot útil

### 2.2 Entrada de dados

- [ ] Aceitar **CSV** e **Excel (.xlsx)**
- [ ] Mínimo **1.500 leads** por importação
- [ ] Colunas obrigatórias:

  | Coluna | Obrigatório | Observação |
  |--------|-------------|------------|
  | `nome` | Sim | |
  | `empresa` | Sim | |
  | `cargo` | Sim | |
  | `instagram` | Sim | Handle (`@usuario`) ou URL do perfil |
  | `cidade` | Não | |
  | `observacoes` | Não | |

- [ ] **Validação automática** (formato handle Instagram, campos vazios, perfil inexistente se checável)
- [ ] **Remoção de duplicados** (por handle Instagram normalizado, sem `@`)
- [ ] Preview da importação antes de confirmar
- [ ] Relatório de linhas rejeitadas com motivo

### 2.3 Sistema de mensagens

- [ ] Até **3 etapas de follow-up** por lead:
  - **Dia 1** — primeira abordagem (DM)
  - **Dia 4** — follow-up 1
  - **Dia 8** — follow-up 2
- [ ] **Personalização avançada** com variáveis: `{{nome}}`, `{{empresa}}`, `{{cargo}}`, `{{cidade}}`, `{{observacoes}}`, `{{instagram}}`
- [ ] **Spintax** para variações automáticas: `{Olá|Oi|E aí} {{nome}}!`
- [ ] Geração de mensagens **diferentes por envio** (variáveis + spintax + hash de unicidade)
- [ ] Templates separados por etapa (D1, D4, D8)
- [ ] Cancelamento automático de follow-ups pendentes se lead **responder** na DM

### 2.4 Canal de envio — Instagram Direct (v1)

Implementação modular via **adapter**. Instagram na v1; demais canais como extensão futura.

| Aspecto | Especificação |
|---------|---------------|
| **Integração** | `instagrapi` ou API privada via sessão/cookies |
| **Tipo de mensagem** | Direct Message (DM) texto |
| **Multi-contas** | Rotação round-robin entre contas Instagram configuradas |
| **Autenticação** | Login por conta (usuário/senha + 2FA) ou import de sessão |
| **Limite Instagram** | ~50–80 DMs/dia/conta nova; escalar com múltiplas contas |
| **Detecção resposta** | Polling periódico da inbox por conta |

**Adapter interface (comum a futuros canais):**

```python
class ChannelAdapter(Protocol):
    async def send(self, lead: Lead, message: str, account: Account) -> SendResult: ...
    async def check_status(self, account: Account) -> AccountStatus: ...
    async def check_replies(self, account: Account) -> list[Reply]: ...
    async def warmup_step(self, account: Account) -> None: ...
```

**Canais futuros (pós-v1):**

| Canal | Integração |
|-------|------------|
| Email | Gmail API / SMTP |
| WhatsApp | Evolution API ou Baileys |
| LinkedIn | Cookies + sessão + proxies |

### 2.5 Anti-ban e segurança (obrigatório)

Específico para Instagram + genérico:

- [ ] **Rate limiting** configurável por conta (default conservador: ~50 DMs/dia/conta)
- [ ] **Delay aleatório** entre mensagens (min/max em segundos, default 120–300)
- [ ] **Rotação de contas** Instagram + **proxies** + **user-agents**
- [ ] **Warm-up de contas** (ramp-up gradual):
  - Dia 1 → 20 DMs
  - Dia 2 → 40 DMs
  - Dia 3 → 60 DMs
  - Dia 4+ → cota proporcional até atingir 150/dia total (split entre contas)
- [ ] **Comportamento humano**: pausas aleatórias, variação de horários, spintax
- [ ] **Logs detalhados** de cada ação (envio, retry, erro, bloqueio, challenge)
- [ ] **Pausa automática** da campanha se detectar:
  - `ChallengeRequired` / checkpoint Instagram
  - `PleaseWaitFewMinutes` / rate limit
  - Conta deslogada ou sessão expirada
  - Erro repetido (threshold configurável)
  - Suspeita de shadowban (taxa de falha > X%)
- [ ] Notificação no dashboard + log quando pausa automática ocorrer

### 2.6 Dashboard e controle

Painel React em **tempo real** (WebSocket ou TanStack Query polling):

| Indicador | Descrição |
|-----------|-----------|
| Enviadas hoje | Contador vs. meta (150) |
| Progresso 10 dias | Barra Dia X/10 + % total |
| Taxa de entrega | DMs enviadas / tentadas |
| Taxa de resposta | Leads que responderam na DM / total contactados |
| Leads restantes | Fila pendente + follow-ups futuros |
| Contas ativas | Status de cada conta Instagram (ok / challenge / ban) |
| Fila atual | Próximos 10 envios agendados |

**Ações:**

- [ ] Pausar campanha
- [ ] Retomar campanha
- [ ] Cancelar campanha (com confirmação)
- [ ] Exportar logs / relatório CSV

### 2.7 Tecnologia

| Camada | Stack |
|--------|-------|
| Backend | **Python 3.12+**, **FastAPI**, SQLAlchemy, Alembic |
| Banco | **SQLite** (dev) / **PostgreSQL** (prod) |
| Fila / Scheduler | **Celery + Redis** |
| CLI | **Typer** + **Rich** (output formatado) |
| Frontend | **React** + **Vite** + **Tailwind** + **TanStack Query** + **TanStack Router** |
| Instagram | **instagrapi** (ou wrapper custom) |
| Config | `.env` + pydantic-settings |
| Container | **Docker opcional** (`docker-compose.yml`) |
| Docs | README completo + docstrings |

Princípios: código **modular**, **limpo** e **bem documentado**.

---

## 3. Arquitetura

```
                    ┌─────────────────┐
                    │   CLI (Typer)   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ Dashboard React │
                    │  (Vite + TW)    │
                    └────────┬────────┘
                             │ REST + WebSocket
                    ┌────────▼────────┐
                    │   FastAPI API   │
                    └────────┬────────┘
         ┌───────────────────┼───────────────────┐
         │                   │                   │
  ┌──────▼──────┐    ┌───────▼───────┐   ┌──────▼──────┐
  │  Campaign   │    │ Lead Manager  │   │  Template   │
  │  Manager    │    │               │   │  Engine     │
  └──────┬──────┘    └───────┬───────┘   └──────┬──────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │
                    ┌────────▼────────┐
                    │    Scheduler    │
                    │  (Celery+Redis) │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ Instagram Adapter│
                    │   (instagrapi)  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ Anti-ban Layer  │
                    │ (rate/proxy/UA) │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ SQLite / PG     │
                    │ + Redis (queue) │
                    └─────────────────┘
```

---

## 4. Módulos

### 4.1 Importador (`services/importer/`)

- Parse CSV/XLSX (pandas + openpyxl)
- Validação de schema e tipos
- Normalização de handle Instagram (remove `@`, lowercase, extrai de URL)
- Dedup por handle normalizado
- Preview + confirmação via API/CLI

### 4.2 Lead Manager (`services/leads/`)

**Estados do lead:**

```
novo → agendado → enviado_d1 → aguardando_d4 → enviado_d4 → aguardando_d8 → enviado_d8 → concluido
                      ↓              ↓              ↓
                   respondido    respondido     respondido
                      ↓              ↓              ↓
                   concluido      concluido      concluido

Qualquer estado → falhou | pausado
```

### 4.3 Campaign Manager (`services/campaigns/`)

Configuração por campanha:

- Nome, templates (D1/D4/D8)
- `messages_per_day` (default 150)
- `duration_days` (default 10)
- `window_start` / `window_end` (default 09:00–18:00)
- `min_interval_sec` / `max_interval_sec` (default 120–300)
- Contas Instagram associadas
- Status: `draft` | `active` | `paused` | `completed` | `cancelled` | `auto_paused`

### 4.4 Scheduler (`services/scheduler/`)

Responsabilidades:

1. Ao iniciar campanha, distribuir 150 slots aleatórios entre 09h–18h
2. Respeitar intervalo mínimo entre envios consecutivos
3. Distribuir carga entre contas Instagram (round-robin + warm-up)
4. Agendar follow-ups (D+3 e D+7 após envio anterior)
5. Polling de inbox para detectar respostas
6. Retry com backoff em falhas transientes
7. Pausar campanha em erros críticos (challenge, ban)
8. Gerar estatísticas diárias

**Exemplo de distribuição (Dia 1, 3 contas):**

```
09:03 → Lead #001  (conta A)
09:08 → Lead #002  (conta B)
09:14 → Lead #003  (conta C)
...
17:53 → Lead #150  (conta B)
```

### 4.5 Template Engine (`services/templates/`)

- Renderização de variáveis `{{campo}}`
- Parser Spintax `{A|B|C}` com seed por lead+etapa (reprodutível mas variado)
- Validação de template (variáveis não resolvidas → erro)
- Preview com lead de exemplo

### 4.6 Instagram Adapter (`adapters/instagram.py`)

| Função | Descrição |
|--------|-----------|
| `login()` | Autentica conta (user/pass/2FA ou sessão) |
| `send_dm()` | Envia DM para handle do lead |
| `check_inbox()` | Verifica respostas na inbox |
| `get_account_status()` | Sessão válida, challenge pendente, etc. |
| `resolve_user_id()` | Converte handle → user_id Instagram |

Dependências: `instagrapi`, proxy opcional por conta.

### 4.7 Anti-ban (`services/antiban/`)

- Rate limiter por conta Instagram (token bucket)
- Rotação round-robin de contas ativas
- Proxy pool por conta (configurável via `.env`)
- User-agent rotation
- Warm-up progressivo (ver §2.5)
- Detector de bloqueio (padrões instagrapi: `ChallengeRequired`, `FeedbackRequired`, etc.)
- Circuit breaker: N falhas consecutivas → pausa automática

### 4.8 Logs e auditoria (`services/logging/`)

Campos por evento:

| Campo | Exemplo |
|-------|---------|
| `timestamp` | 2026-07-31T14:23:01Z |
| `campaign_id` | uuid |
| `lead_id` | uuid |
| `action` | `send` / `retry` / `followup` / `pause` / `reply_detected` |
| `channel` | `instagram` |
| `account_id` | uuid |
| `instagram_handle` | `@lead_user` |
| `result` | `success` / `failed` / `blocked` / `challenge` |
| `error` | mensagem de erro |
| `message_hash` | hash do conteúdo enviado |

Filtros: hoje, ontem, campanha, lead, conta, resultado.

---

## 5. Banco de dados

### Tabelas principais

| Tabela | Descrição |
|--------|-----------|
| `users` | Usuário local (v1 single-user) |
| `campaigns` | Configuração e status da campanha |
| `leads` | Dados do lead + handle Instagram + estado |
| `messages` | Histórico de DMs (conteúdo, etapa, resultado) |
| `templates` | Templates D1/D4/D8 por campanha |
| `accounts` | Contas Instagram (sessão, proxy, status, warm-up day) |
| `scheduled_jobs` | Fila de envios com horário + conta atribuída |
| `followups` | Follow-ups pendentes/concluídos |
| `replies` | Respostas detectadas na inbox |
| `logs` | Auditoria detalhada |
| `metrics_daily` | Agregados por dia (enviadas, respostas) |

---

## 6. Estrutura do projeto

```
prospectai-scale/
├── backend/
│   ├── api/                 # Rotas FastAPI
│   │   ├── campaigns.py
│   │   ├── leads.py
│   │   ├── templates.py
│   │   ├── accounts.py
│   │   ├── logs.py
│   │   └── dashboard.py
│   ├── adapters/
│   │   └── instagram.py     # v1
│   ├── services/
│   │   ├── importer/
│   │   ├── campaigns/
│   │   ├── leads/
│   │   ├── scheduler/
│   │   ├── templates/
│   │   ├── antiban/
│   │   └── logging/
│   ├── database/
│   │   ├── models/
│   │   └── migrations/      # Alembic
│   ├── schemas/             # Pydantic
│   ├── utils/
│   ├── cli/                 # Typer CLI
│   └── main.py
├── frontend/                # React SPA
│   ├── src/
│   │   ├── routes/          # TanStack Router (file-based)
│   │   ├── components/
│   │   ├── lib/api/         # fetch client
│   │   └── hooks/
│   ├── package.json
│   └── vite.config.ts
├── docker/
├── docs/
├── examples/
│   └── leads_1500.csv       # 1.500 leads fictícios
├── .env.example
├── docker-compose.yml       # opcional
├── pyproject.toml
└── README.md
```

---

## 7. Dashboard React — telas

| Rota | Conteúdo |
|------|----------|
| `/` | KPIs tempo real, progresso 10 dias, gráfico envios/dia |
| `/campanhas` | Criar, editar, pausar, retomar, cancelar |
| `/campanhas/:id` | Detalhe da campanha + fila de envios |
| `/leads` | Lista, filtros por estado, importar CSV/XLSX |
| `/templates` | Editor D1/D4/D8 com preview Spintax |
| `/contas` | Gerenciar contas Instagram (login, status, proxy) |
| `/logs` | Tabela filtrável + export CSV |
| `/configuracoes` | Rate limits, delays, warm-up, proxies |

---

## 8. CLI — comandos

```bash
prospectai import leads.csv --campaign "Campanha Q3"
prospectai campaign create --name "Campanha Q3" --channel instagram
prospectai campaign start <id>
prospectai campaign pause <id>
prospectai campaign resume <id>
prospectai campaign status <id>
prospectai accounts add --username minha_conta --password '***'
prospectai accounts login <id>                    # re-autenticar sessão
prospectai accounts status                        # status de todas as contas
prospectai logs --campaign <id> --today
```

---

## 9. Docker (opcional)

```yaml
services:
  api:        # FastAPI
  worker:     # Celery worker
  beat:       # Celery beat (scheduler)
  redis:      # Fila
  postgres:   # Banco (prod)
  frontend:   # nginx servindo build React
```

---

## 10. Entregáveis

| # | Entregável | Status |
|---|------------|--------|
| 1 | Estrutura completa do projeto | ⬜ |
| 2 | Código funcional — Instagram Direct + anti-ban | ⬜ |
| 3 | CLI Typer completa | ⬜ |
| 4 | Dashboard React com KPIs tempo real | ⬜ |
| 5 | Exemplo CSV com 1.500 leads fictícios | ⬜ |
| 6 | README detalhado (instalação, uso, `.env`) | ⬜ |
| 7 | Instruções de escala com múltiplas contas Instagram | ⬜ |
| 8 | Docker Compose opcional | ⬜ |

---

## 11. Escalabilidade

### v1 — múltiplas contas Instagram

Para atingir 150 DMs/dia com segurança:

| Contas | DMs/conta/dia | Total/dia |
|--------|---------------|-----------|
| 3 | ~50 | 150 |
| 5 | ~30 | 150 |
| 10 | ~15 | 150 |

Recomendação: **3–5 contas** com warm-up de 4 dias cada.

### Pós-v1

- Múltiplas campanhas simultâneas
- Múltiplos usuários / autenticação JWT
- Múltiplos workers Celery
- Adapters Email, WhatsApp, LinkedIn
- Webhook para integração CRM (HubSpot, Pipedrive)

---

## 12. Fases de implementação

| Fase | Escopo | Estimativa |
|------|--------|------------|
| **F1 — Core** | Models, DB, importador, CLI básica | 2–3 dias |
| **F2 — Scheduler** | Distribuição 150/dia, intervalos, follow-ups | 2–3 dias |
| **F3 — Instagram** | Adapter instagrapi, login, send DM, inbox polling | 3–4 dias |
| **F4 — Anti-ban** | Rate limit, rotação, warm-up, circuit breaker | 2–3 dias |
| **F5 — Templates** | Variáveis + Spintax + preview | 1–2 dias |
| **F6 — Dashboard React** | KPIs tempo real, campanhas, contas, logs | 3–4 dias |
| **F7 — Polish** | README, CSV exemplo, Docker, testes | 1–2 dias |

**Total estimado:** 14–21 dias de desenvolvimento.

---

## 13. README — conteúdo obrigatório

- [ ] Requisitos (Python 3.12+, Node 20+, Redis, PostgreSQL)
- [ ] Instalação local (backend + frontend)
- [ ] Configuração `.env` (contas Instagram, proxies, Redis, DB)
- [ ] Importar leads (CSV/XLSX)
- [ ] Configurar contas Instagram e warm-up
- [ ] Criar campanha e templates
- [ ] Iniciar campanha (CLI ou dashboard)
- [ ] Acompanhar métricas e logs
- [ ] Escalar com múltiplas contas Instagram
- [ ] Backup e restore
- [ ] Troubleshooting (challenge Instagram, sessão expirada, shadowban, rate limit)
