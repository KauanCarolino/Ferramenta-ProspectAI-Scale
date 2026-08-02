"""CLI Typer do ProspectAI."""

from __future__ import annotations

import sys
from pathlib import Path

# Garante que backend/ seja importável ao invocar como `python -m cli` ou console script
# a partir de um checkout sem install editável dos módulos irmãos.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import uuid
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models.account import Account
from database.models.campaign import Campaign
from database.models.lead import Lead
from database.session import SessionLocal, init_db
from schemas.account import AccountCreate
from schemas.campaign import CampaignCreate
from services import accounts as account_service
from services import campaigns as campaign_service
from services.accounts.service import login_account, process_inbox_replies, resolve_account_challenge
from services.importer.service import confirm_import, preview_import
from services.logging.service import list_logs
from services.scheduler.service import list_campaign_jobs
from services.scheduler.worker import process_due_jobs
from services.sourcing.service import pull_and_confirm_followers

app = typer.Typer(name="prospectai", help="ProspectAI Scale — CLI operacional", no_args_is_help=True)
campaign_app = typer.Typer(help="Gerenciar campanhas")
accounts_app = typer.Typer(help="Gerenciar contas Instagram")
scheduler_app = typer.Typer(help="Scheduler / fila de envios")
antiban_app = typer.Typer(help="Anti-ban / rate limits")
templates_app = typer.Typer(help="Templates / preview Spintax")
app.add_typer(campaign_app, name="campaign")
app.add_typer(accounts_app, name="accounts")
app.add_typer(scheduler_app, name="scheduler")
app.add_typer(antiban_app, name="antiban")
app.add_typer(templates_app, name="templates")

console = Console()


def _db() -> Session:
    init_db()
    return SessionLocal()


@app.command("import")
def import_leads(
    file: Path = typer.Argument(..., exists=True, readable=True, help="CSV ou XLSX"),
    campaign: str = typer.Option(..., "--campaign", "-c", help="Nome ou UUID da campanha"),
    confirm: bool = typer.Option(False, "--confirm", help="Persistir leads válidos"),
) -> None:
    """Importar leads de CSV/XLSX para uma campanha."""
    db = _db()
    try:
        campaign_obj = _resolve_campaign(db, campaign)
        existing = {
            row[0]
            for row in db.execute(
                select(Lead.instagram).where(Lead.campaign_id == campaign_obj.id)
            ).all()
        }
        result = preview_import(
            file,
            filename=file.name,
            campaign_id=campaign_obj.id,
            existing_handles=existing,
        )
        console.print(
            f"[bold]Pré-visualização[/bold] total={result.total_rows} "
            f"válidos={result.valid_count} rejeitados={result.rejected_count} "
            f"dups={result.duplicate_count}"
        )
        if result.rejected:
            table = Table(title="Rejeitados")
            table.add_column("Linha")
            table.add_column("Motivos")
            for row in result.rejected[:20]:
                table.add_row(str(row.row_number), "; ".join(row.reasons))
            console.print(table)

        if confirm:
            confirmed = confirm_import(db, campaign_id=campaign_obj.id, preview=result)
            console.print(
                f"[green]Importado:[/green] inseridos={confirmed.inserted} "
                f"ignorados={confirmed.skipped_duplicates}"
            )
        else:
            console.print("[yellow]Simulação[/yellow] — use --confirm para persistir.")
    finally:
        db.close()


@app.command("pull-followers")
def pull_followers(
    campaign: str = typer.Option(..., "--campaign", "-c", help="Nome ou UUID da campanha"),
    account: str = typer.Option(..., "--account", "-a", help="Username ou UUID da conta Instagram"),
    amount: int = typer.Option(150, "--amount", "-n", help="Quantidade de seguidores a importar"),
    start: bool = typer.Option(
        False, "--start", help="Já iniciar a campanha (agenda envios respeitando anti-ban)."
    ),
) -> None:
    """Puxar seguidores da conta e importar como leads — sem planilha, sem 1 a 1."""
    db = _db()
    try:
        campaign_obj = _resolve_campaign(db, campaign)
        account_obj = _resolve_account(db, account)
        result = pull_and_confirm_followers(
            db,
            campaign_id=campaign_obj.id,
            account_id=account_obj.id,
            amount=amount,
        )
        console.print(
            f"[green]Seguidores importados[/green] inseridos={result.inserted} "
            f"ignorados={result.skipped_duplicates}"
        )
        if start:
            started = campaign_service.start_campaign(db, campaign_obj.id)
            console.print(f"[green]Campanha iniciada[/green] {started.id} → {started.status}")
        else:
            console.print(
                "[dim]Dica:[/dim] rode "
                f"[cyan]prospectai campaign start {campaign_obj.id}[/cyan] "
                "para começar o envio automático (respeitando anti-ban)."
            )
    finally:
        db.close()


@campaign_app.command("create")
def campaign_create(
    name: str = typer.Option(..., "--name", "-n"),
    channel: str = typer.Option("instagram", "--channel"),
) -> None:
    db = _db()
    try:
        created = campaign_service.create_campaign(
            db, CampaignCreate(name=name, channel=channel)
        )
        console.print(f"[green]Campanha criada[/green] id={created.id} status={created.status}")
    finally:
        db.close()


@campaign_app.command("start")
def campaign_start(campaign_id: str = typer.Argument(...)) -> None:
    db = _db()
    try:
        cid = uuid.UUID(campaign_id)
        campaign = campaign_service.start_campaign(db, cid)
        console.print(f"[green]Iniciada[/green] {campaign.id} → {campaign.status}")
    finally:
        db.close()


@campaign_app.command("pause")
def campaign_pause(campaign_id: str = typer.Argument(...)) -> None:
    db = _db()
    try:
        campaign = campaign_service.pause_campaign(db, uuid.UUID(campaign_id))
        console.print(f"[yellow]Pausada[/yellow] {campaign.id}")
    finally:
        db.close()


@campaign_app.command("cancel")
def campaign_cancel(campaign_id: str = typer.Argument(...)) -> None:
    db = _db()
    try:
        campaign = campaign_service.cancel_campaign(db, uuid.UUID(campaign_id))
        console.print(f"[red]Cancelada[/red] {campaign.id}")
    finally:
        db.close()


@campaign_app.command("resume")
def campaign_resume(campaign_id: str = typer.Argument(...)) -> None:
    db = _db()
    try:
        campaign = campaign_service.resume_campaign(db, uuid.UUID(campaign_id))
        console.print(f"[green]Retomada[/green] {campaign.id}")
    finally:
        db.close()


@campaign_app.command("status")
def campaign_status(campaign_id: str = typer.Argument(...)) -> None:
    db = _db()
    try:
        campaign = campaign_service.get_campaign(db, uuid.UUID(campaign_id))
        console.print(
            f"id={campaign.id}\nname={campaign.name}\nstatus={campaign.status}\n"
            f"channel={campaign.channel}\nmessages_per_day={campaign.messages_per_day}"
        )
    finally:
        db.close()


@accounts_app.command("add")
def accounts_add(
    username: str = typer.Option(..., "--username", "-u"),
    password: Optional[str] = typer.Option(None, "--password", "-p", help="Não persistido"),
    proxy: Optional[str] = typer.Option(None, "--proxy"),
) -> None:
    db = _db()
    try:
        account = account_service.create_account(
            db, AccountCreate(username=username, password=password, proxy=proxy)
        )
        console.print(f"[green]Conta adicionada[/green] id={account.id} status={account.status}")
        if password:
            console.print(
                "[dim]Senha descartada — use[/dim] "
                f"[cyan]prospectai accounts login {account.id} --password ...[/cyan]"
            )
    finally:
        db.close()


@accounts_app.command("status")
def accounts_status() -> None:
    db = _db()
    try:
        rows = account_service.list_accounts(db, limit=200)
        table = Table(title="Contas Instagram")
        table.add_column("ID")
        table.add_column("Usuário")
        table.add_column("Status")
        table.add_column("Warm-up")
        table.add_column("Proxy")
        for acc in rows:
            table.add_row(
                str(acc.id),
                acc.username,
                acc.status,
                str(acc.warmup_day),
                acc.proxy or "-",
            )
        console.print(table)
    finally:
        db.close()


@accounts_app.command("login")
def accounts_login(
    account_id: str = typer.Argument(..., help="UUID da conta"),
    password: Optional[str] = typer.Option(
        None,
        "--password",
        "-p",
        help="Senha Instagram (nunca persistida). Se omitida, pede prompt seguro.",
    ),
    verification_code: Optional[str] = typer.Option(
        None,
        "--2fa",
        "--verification-code",
        help="Código 2FA (nunca persistido).",
    ),
    challenge_code: Optional[str] = typer.Option(
        None,
        "--code",
        "--challenge-code",
        help="Código do checkpoint email/SMS (nunca persistido).",
    ),
    challenge_choice: str = typer.Option(
        "email",
        "--choice",
        help="Canal do checkpoint: email ou sms.",
    ),
) -> None:
    """Autenticar conta e gravar sessão em sessions_dir."""
    if challenge_choice not in {"email", "sms"}:
        console.print("[red]--choice deve ser email ou sms[/red]")
        raise typer.Exit(code=1)
    pwd = password if password is not None else typer.prompt("Senha Instagram", hide_input=True)
    db = _db()
    try:
        outcome = login_account(
            db,
            uuid.UUID(account_id),
            pwd,
            verification_code=verification_code,
            challenge_code=challenge_code,
            challenge_choice=challenge_choice,
        )
        account = outcome.account
        color = "green" if account.status == "active" else "yellow"
        console.print(f"[{color}]Login[/] id={account.id} status={account.status}")
        if account.status == "challenge":
            if outcome.two_factor_pending:
                console.print(
                    "[yellow]2FA pendente.[/yellow] "
                    "Reenvie com [cyan]--2fa CODIGO[/cyan]."
                )
            elif outcome.challenge_pending:
                console.print(
                    "[yellow]Checkpoint pendente.[/yellow] "
                    "Use [cyan]accounts challenge ACCOUNT_ID --code ...[/cyan] "
                    "ou relogue com [cyan]--code[/cyan]."
                )
            else:
                console.print(
                    "[yellow]Challenge/2FA pendente.[/yellow] "
                    "Use [cyan]accounts challenge ACCOUNT_ID --code ...[/cyan] "
                    "ou relogue com [cyan]--code[/cyan] / [cyan]--2fa[/cyan]."
                )
            raise typer.Exit(code=2)
        if account.status != "active":
            raise typer.Exit(code=1)
    except Exception as exc:
        if isinstance(exc, typer.Exit):
            raise
        console.print(f"[red]Login falhou:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    finally:
        db.close()


@accounts_app.command("challenge")
def accounts_challenge(
    account_id: str = typer.Argument(..., help="UUID da conta"),
    code: str = typer.Option(..., "--code", "-c", help="Código email/SMS (nunca persistido)"),
    choice: str = typer.Option("email", "--choice", help="email ou sms"),
) -> None:
    """Resolver checkpoint ChallengeRequired com código recebido."""
    if choice not in {"email", "sms"}:
        console.print("[red]--choice deve ser email ou sms[/red]")
        raise typer.Exit(code=1)
    db = _db()
    try:
        outcome = resolve_account_challenge(
            db,
            uuid.UUID(account_id),
            code,
            choice=choice,
        )
        account = outcome.account
        color = "green" if account.status == "active" else "yellow"
        console.print(f"[{color}]Challenge[/] id={account.id} status={account.status}")
        if account.status != "active":
            console.print("[yellow]Ainda pendente — verifique o código e tente novamente.[/yellow]")
            raise typer.Exit(code=2)
    except Exception as exc:
        if isinstance(exc, typer.Exit):
            raise
        console.print(f"[red]Challenge falhou:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    finally:
        db.close()


@accounts_app.command("inbox-poll")
def accounts_inbox_poll(
    account: Optional[str] = typer.Option(None, "--account", "-a", help="UUID da conta (opcional)"),
) -> None:
    """Polling da inbox — marca leads respondidos e cancela follow-ups pendentes."""
    db = _db()
    try:
        account_id = uuid.UUID(account) if account else None
        result = process_inbox_replies(db, account_id=account_id)
        console.print(
            f"[green]Inbox poll[/green] contas={result['accounts_polled']} "
            f"respostas={result['replies_seen']} leads={result['leads_matched']} "
            f"erros={result['errors']}"
        )
    finally:
        db.close()


@scheduler_app.command("run-due")
def scheduler_run_due(
    limit: int = typer.Option(100, "--limit", "-n", help="Máximo de jobs a processar"),
    campaign: Optional[str] = typer.Option(None, "--campaign", "-c", help="UUID da campanha"),
) -> None:
    """Processar jobs pendentes com scheduled_at <= agora (fallback sync sem Redis)."""
    db = _db()
    try:
        campaign_id = uuid.UUID(campaign) if campaign else None
        result = process_due_jobs(db, limit=limit, campaign_id=campaign_id)
        console.print(
            f"[green]Jobs vencidos[/green] processados={result['processed']} "
            f"ok={result['succeeded']} falha={result['failed']} skip={result['skipped']}"
        )
    finally:
        db.close()


@scheduler_app.command("list")
def scheduler_list(
    campaign_id: str = typer.Argument(..., help="UUID da campanha"),
    limit: int = typer.Option(20, "--limit", "-n"),
    status: Optional[str] = typer.Option("pending", "--status", "-s"),
) -> None:
    """Listar próximos jobs de uma campanha."""
    db = _db()
    try:
        jobs = list_campaign_jobs(db, uuid.UUID(campaign_id), limit=limit, status=status)
        table = Table(title=f"Jobs ({status or 'todos'})")
        table.add_column("Agendado em")
        table.add_column("Etapa")
        table.add_column("Status")
        table.add_column("Lead")
        table.add_column("Conta")
        for job in jobs:
            table.add_row(
                job.scheduled_at.isoformat(),
                job.stage,
                job.status,
                str(job.lead_id)[:8],
                str(job.account_id)[:8] if job.account_id else "-",
            )
        console.print(table)
        console.print(f"Total: {len(jobs)}")
    finally:
        db.close()


@antiban_app.command("status")
def antiban_status(
    account: Optional[str] = typer.Option(None, "--account", "-a", help="UUID da conta"),
) -> None:
    """Mostrar cota diária / warm-up / rate limit por conta."""
    from config import get_settings
    from services.antiban import account_antiban_status

    db = _db()
    try:
        settings = get_settings()
        console.print(
            f"[bold]Anti-ban[/bold] max/day={settings.antiban_max_dm_per_account_per_day} "
            f"delay={settings.antiban_min_delay_sec}-{settings.antiban_max_delay_sec}s "
            f"warmup={'on' if settings.antiban_warmup_enabled else 'off'} "
            f"threshold={settings.antiban_consecutive_failure_threshold}"
        )
        if account:
            rows = [account_service.get_account(db, uuid.UUID(account))]
        else:
            rows = account_service.list_accounts(db, limit=200)
        table = Table(title="Contas")
        table.add_column("Usuário")
        table.add_column("Status")
        table.add_column("Warm")
        table.add_column("Hoje")
        table.add_column("Cap")
        table.add_column("OK?")
        table.add_column("Motivo")
        for acc in rows:
            snap = account_antiban_status(db, acc)
            table.add_row(
                str(snap["username"]),
                str(snap["status"]),
                f"{snap['warmup_day']}→{snap['effective_warmup_day']}",
                f"{snap['messages_today']}/{snap['daily_cap']}",
                str(snap["daily_cap"]),
                "yes" if snap["rate_limit_allowed"] else "no",
                str(snap["rate_limit_reason"]),
            )
        console.print(table)
    finally:
        db.close()


@templates_app.command("preview")
def templates_preview(
    body: str = typer.Option(..., "--body", "-b", help="Texto do template"),
    nome: Optional[str] = typer.Option(None, "--nome"),
    empresa: Optional[str] = typer.Option(None, "--empresa"),
    cargo: Optional[str] = typer.Option(None, "--cargo"),
    cidade: Optional[str] = typer.Option(None, "--cidade"),
    observacoes: Optional[str] = typer.Option(None, "--observacoes"),
    instagram: Optional[str] = typer.Option(None, "--instagram"),
    seed: Optional[str] = typer.Option(None, "--seed", "-s", help="Seed Spintax"),
) -> None:
    """Pré-visualizar renderização de variáveis + Spintax."""
    from fastapi import HTTPException

    from schemas.template import TemplatePreviewRequest
    from services.templates.service import preview_template, validate_template_body

    variables = {
        "nome": nome,
        "empresa": empresa,
        "cargo": cargo,
        "cidade": cidade,
        "observacoes": observacoes,
        "instagram": instagram,
    }
    issues = validate_template_body(body)
    if issues:
        for msg in issues:
            console.print(f"[red]{msg}[/red]")
        raise typer.Exit(code=1)

    try:
        result = preview_template(
            TemplatePreviewRequest(body=body, variables=variables, seed=seed)
        )
    except HTTPException as exc:
        console.print(f"[red]{exc.detail}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(f"[bold]Rendered:[/bold] {result.rendered}")
    console.print(f"variables_used={result.variables_used} spintax_groups={result.spintax_groups}")


@app.command("logs")
def show_logs(
    campaign: Optional[str] = typer.Option(None, "--campaign", "-c"),
    today: bool = typer.Option(False, "--today"),
    limit: int = typer.Option(50, "--limit", "-n"),
) -> None:
    db = _db()
    try:
        campaign_id = uuid.UUID(campaign) if campaign else None
        rows = list_logs(db, campaign_id=campaign_id, today_only=today, limit=limit)
        table = Table(title="Logs")
        table.add_column("Data/hora")
        table.add_column("Ação")
        table.add_column("Resultado")
        table.add_column("Handle Instagram")
        table.add_column("Erro")
        for row in rows:
            table.add_row(
                row.timestamp.isoformat(),
                row.action,
                row.result,
                row.instagram_handle or "-",
                (row.error or "-")[:60],
            )
        console.print(table)
    finally:
        db.close()


def _resolve_campaign(db: Session, campaign: str) -> Campaign:
    try:
        cid = uuid.UUID(campaign)
        return campaign_service.get_campaign(db, cid)
    except ValueError:
        pass
    obj = db.scalar(select(Campaign).where(Campaign.name == campaign))
    if obj is None:
        console.print(f"[red]Campanha não encontrada:[/red] {campaign}")
        raise typer.Exit(code=1)
    return obj


def _resolve_account(db: Session, account: str) -> Account:
    try:
        aid = uuid.UUID(account)
        obj = db.get(Account, aid)
    except ValueError:
        obj = db.scalar(select(Account).where(Account.username == account.lstrip("@")))
    if obj is None:
        console.print(f"[red]Conta não encontrada:[/red] {account}")
        raise typer.Exit(code=1)
    return obj


def main() -> None:
    app()


if __name__ == "__main__":
    main()
