"""Adapter do Instagram Direct (canal v1).

Protocol + Stub (testes/CI) + InstagrapiAdapter (produção via ``INSTAGRAM_ADAPTER``).

Challenge / 2FA: handlers nunca bloqueiam em stdin (uvicorn). Login sem código
persiste sidecar ``{session}.challenge.json``; ``resolve_challenge`` retoma.
TwoFactorRequired → status ``challenge`` + detail ``two_factor_required``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

ChallengeChoiceStr = Literal["email", "sms"]


@dataclass
class LoginResult:
    """Resultado rico de login / resolve_challenge (não só bool)."""

    success: bool
    challenge_pending: bool = False
    two_factor_pending: bool = False
    detail: str | None = None


@dataclass
class AccountStatusInfo:
    username: str
    session_valid: bool
    challenge_pending: bool
    two_factor_pending: bool = False
    detail: str = ""


@dataclass
class SendResult:
    success: bool
    message_id: str | None = None
    error: str | None = None
    blocked: bool = False
    challenge: bool = False


@dataclass
class InboxReply:
    thread_id: str
    username: str
    text: str
    message_id: str | None = None


@runtime_checkable
class InstagramAdapter(Protocol):
    """Contrato de canal para Instagram Direct."""

    def login(
        self,
        username: str,
        password: str,
        *,
        proxy: str | None = None,
        verification_code: str | None = None,
        challenge_code: str | None = None,
        challenge_choice: ChallengeChoiceStr | None = None,
    ) -> LoginResult:
        """Autentica e persiste a sessão. Pode retornar challenge/2FA pendente."""
        ...

    def resolve_challenge(
        self,
        code: str,
        *,
        choice: ChallengeChoiceStr = "email",
    ) -> LoginResult:
        """Retoma checkpoint com código email/SMS (sidecar + sessão)."""
        ...

    def send_dm(self, username: str, text: str) -> SendResult:
        """Envia uma DM para ``username`` (handle sem @)."""
        ...

    def check_inbox(self, *, since_id: str | None = None) -> list[InboxReply]:
        """Consulta a inbox por novas respostas."""
        ...

    def get_account_status(self) -> AccountStatusInfo:
        """Retorna o estado da sessão / challenge / 2FA."""
        ...

    def resolve_user_id(self, username: str) -> str | None:
        """Mapeia handle → id de usuário do Instagram."""
        ...


class StubInstagramAdapter:
    """Adapter simulado — default em testes/CI (sem rede)."""

    def __init__(
        self,
        username: str | None = None,
        *,
        session_path: str | None = None,
        proxy: str | None = None,
    ) -> None:
        self.username = username or "stub"
        self.session_path = session_path
        self.proxy = proxy

    def login(
        self,
        username: str,
        password: str,
        *,
        proxy: str | None = None,
        verification_code: str | None = None,
        challenge_code: str | None = None,
        challenge_choice: ChallengeChoiceStr | None = None,
    ) -> LoginResult:
        # Senha/códigos nunca são logados; stub não persiste sessão real.
        _ = password, proxy, verification_code, challenge_code, challenge_choice
        logger.info("StubInstagramAdapter.login → @%s (simulado ok)", username)
        self.username = username
        return LoginResult(success=True, detail="stub")

    def resolve_challenge(
        self,
        code: str,
        *,
        choice: ChallengeChoiceStr = "email",
    ) -> LoginResult:
        _ = code, choice
        logger.info("StubInstagramAdapter.resolve_challenge → @%s (simulado ok)", self.username)
        return LoginResult(success=True, detail="stub")

    def send_dm(self, username: str, text: str) -> SendResult:
        logger.info(
            "StubInstagramAdapter.send_dm → @%s (%s chars) [simulado ok]",
            username,
            len(text),
        )
        return SendResult(success=True, message_id=f"stub-{username}")

    def check_inbox(self, *, since_id: str | None = None) -> list[InboxReply]:
        logger.debug("StubInstagramAdapter.check_inbox since_id=%s — lista vazia", since_id)
        return []

    def get_account_status(self) -> AccountStatusInfo:
        return AccountStatusInfo(
            username=self.username,
            session_valid=bool(self.session_path),
            challenge_pending=False,
            two_factor_pending=False,
            detail="stub",
        )

    def resolve_user_id(self, username: str) -> str | None:
        return f"stub-uid-{username}"


class InstagrapiAdapter:
    """Adapter real baseado em ``instagrapi.Client``.

    Sessões em ``session_path`` (sob ``sessions_dir``). Nunca loga senha/códigos.
    Aceita ``client`` injetado para testes unitários (mock).

    Handlers de challenge/password **nunca** usam ``input()`` (bloqueio sob uvicorn).
    ``handle_exception`` re-raise ChallengeRequired / TwoFactorRequired para evitar
    auto-resolve silencioso que cairia no stdin default.
    """

    def __init__(
        self,
        username: str | None = None,
        *,
        session_path: str | None = None,
        proxy: str | None = None,
        client: Any | None = None,
    ) -> None:
        from instagrapi import Client

        self.username = username or ""
        self.session_path = session_path
        self.proxy = proxy
        self._client = client if client is not None else Client()
        self._challenge_pending = False
        self._two_factor_pending = False
        self._session_valid = False
        self._pending_challenge_code: str | None = None
        self._active_challenge_choice: ChallengeChoiceStr = "email"
        self._challenge_choice_resolver_installed = False
        self._install_noninteractive_handlers()
        self._install_challenge_choice_resolver()
        self._apply_proxy(proxy)

    def login(
        self,
        username: str,
        password: str,
        *,
        proxy: str | None = None,
        verification_code: str | None = None,
        challenge_code: str | None = None,
        challenge_choice: ChallengeChoiceStr | None = None,
    ) -> LoginResult:
        from instagrapi.exceptions import ChallengeRequired, LoginRequired, TwoFactorRequired

        self.username = username
        if proxy is not None:
            self.proxy = proxy
            self._apply_proxy(proxy)

        choice: ChallengeChoiceStr = challenge_choice or "email"
        self._active_challenge_choice = choice
        self._pending_challenge_code = challenge_code
        self._install_noninteractive_handlers(challenge_code=challenge_code)

        path = self._session_file()
        try:
            if path is not None and path.is_file():
                logger.info("Carregando sessão existente para @%s", username)
                self._client.load_settings(str(path))
                self._apply_proxy(self.proxy)

            # Nunca logar ``password`` / códigos.
            login_kwargs: dict[str, Any] = {}
            if verification_code:
                login_kwargs["verification_code"] = verification_code
            self._client.login(username, password, **login_kwargs)

            # Se challenge_code veio e o login ainda deixou last_json de challenge
            # (raro com handle_exception re-raise), resolve abaixo no except.
            self._dump_session(path)
            self._clear_challenge_sidecar()
            self._session_valid = True
            self._challenge_pending = False
            self._two_factor_pending = False
            self._pending_challenge_code = None
            logger.info("Login OK para @%s (sessão persistida)", username)
            return LoginResult(success=True, detail="login_ok")
        except ChallengeRequired as exc:
            if challenge_code:
                return self._try_challenge_resolve(challenge_code, choice=choice, path=path)
            return self._persist_challenge_pending(exc, detail="challenge_required")
        except TwoFactorRequired as exc:
            self._challenge_pending = True
            self._two_factor_pending = True
            self._session_valid = False
            # Persiste settings parciais para retomar com verification_code.
            self._dump_session(path)
            logger.warning(
                "TwoFactorRequired no login de @%s: %s",
                username,
                type(exc).__name__,
            )
            return LoginResult(
                success=False,
                challenge_pending=True,
                two_factor_pending=True,
                detail="two_factor_required",
            )
        except LoginRequired as exc:
            self._session_valid = False
            self._challenge_pending = False
            self._two_factor_pending = False
            logger.warning("LoginRequired no login de @%s: %s", username, type(exc).__name__)
            return LoginResult(success=False, detail=f"login_required:{type(exc).__name__}")
        except Exception:
            self._session_valid = False
            logger.exception("Falha no login de @%s", username)
            raise

    def resolve_challenge(
        self,
        code: str,
        *,
        choice: ChallengeChoiceStr = "email",
    ) -> LoginResult:
        """Retoma checkpoint: carrega sessão + sidecar e chama ``challenge_resolve``."""
        path = self._session_file()
        sidecar = self._challenge_sidecar_path()
        if path is None or not path.is_file():
            return LoginResult(
                success=False,
                challenge_pending=True,
                detail="no_session_file",
            )
        if sidecar is None or not sidecar.is_file():
            return LoginResult(
                success=False,
                challenge_pending=True,
                detail="no_challenge_sidecar",
            )

        try:
            last_json = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Sidecar challenge inválido: %s", type(exc).__name__)
            return LoginResult(
                success=False,
                challenge_pending=True,
                detail=f"sidecar_invalid:{type(exc).__name__}",
            )

        self._active_challenge_choice = choice
        self._pending_challenge_code = code
        self._install_noninteractive_handlers(challenge_code=code)

        try:
            self._client.load_settings(str(path))
            self._apply_proxy(self.proxy)
            return self._try_challenge_resolve(code, choice=choice, path=path, last_json=last_json)
        except Exception as exc:
            self._challenge_pending = True
            self._session_valid = False
            logger.warning(
                "resolve_challenge falhou (@%s): %s",
                self.username,
                type(exc).__name__,
            )
            return LoginResult(
                success=False,
                challenge_pending=True,
                detail=type(exc).__name__,
            )

    def send_dm(self, username: str, text: str) -> SendResult:
        from instagrapi.exceptions import (
            ChallengeRequired,
            FeedbackRequired,
            LoginRequired,
            PleaseWaitFewMinutes,
            RateLimitError,
            UserNotFound,
        )

        ready_err = self._ensure_session()
        if ready_err:
            return SendResult(success=False, error=ready_err, challenge=self._challenge_pending)

        try:
            user_id = self.resolve_user_id(username)
            if user_id is None:
                return SendResult(success=False, error=f"user_not_found:{username}")

            message = self._client.direct_send(text, user_ids=[int(user_id)])
            message_id = str(getattr(message, "id", None) or "")
            return SendResult(success=True, message_id=message_id or None)
        except ChallengeRequired as exc:
            self._challenge_pending = True
            self._session_valid = False
            logger.warning("ChallengeRequired ao enviar DM para @%s", username)
            return SendResult(
                success=False,
                error=f"challenge_required:{type(exc).__name__}",
                challenge=True,
            )
        except (FeedbackRequired, PleaseWaitFewMinutes, RateLimitError) as exc:
            logger.warning("Rate/feedback block ao enviar DM para @%s: %s", username, type(exc).__name__)
            return SendResult(
                success=False,
                error=f"blocked:{type(exc).__name__}",
                blocked=True,
            )
        except UserNotFound:
            return SendResult(success=False, error=f"user_not_found:{username}")
        except LoginRequired as exc:
            self._session_valid = False
            return SendResult(success=False, error=f"login_required:{type(exc).__name__}")
        except Exception as exc:
            logger.exception("Erro ao enviar DM para @%s", username)
            return SendResult(success=False, error=f"{type(exc).__name__}:{exc}")

    def check_inbox(self, *, since_id: str | None = None) -> list[InboxReply]:
        from instagrapi.exceptions import ChallengeRequired, LoginRequired

        ready_err = self._ensure_session()
        if ready_err:
            logger.warning("check_inbox sem sessão: %s", ready_err)
            return []

        try:
            threads = self._client.direct_threads(amount=20)
        except ChallengeRequired:
            self._challenge_pending = True
            self._session_valid = False
            logger.warning("ChallengeRequired em check_inbox (@%s)", self.username)
            return []
        except LoginRequired:
            self._session_valid = False
            logger.warning("LoginRequired em check_inbox (@%s)", self.username)
            return []
        except Exception:
            logger.exception("Falha em check_inbox (@%s)", self.username)
            return []

        own_id = self._own_user_id()
        replies: list[InboxReply] = []
        for thread in threads or []:
            thread_id = str(getattr(thread, "id", "") or "")
            peer = self._peer_username(thread, own_id)
            if not peer:
                continue
            for msg in getattr(thread, "messages", None) or []:
                msg_id = str(getattr(msg, "id", "") or "")
                if since_id and msg_id and msg_id <= since_id:
                    continue
                sender_id = getattr(msg, "user_id", None)
                if own_id is not None and sender_id is not None and int(sender_id) == int(own_id):
                    continue
                text = str(getattr(msg, "text", None) or "")
                if not text:
                    continue
                replies.append(
                    InboxReply(
                        thread_id=thread_id,
                        username=peer,
                        text=text,
                        message_id=msg_id or None,
                    )
                )
        return replies

    def get_account_status(self) -> AccountStatusInfo:
        if self._two_factor_pending:
            return AccountStatusInfo(
                username=self.username,
                session_valid=False,
                challenge_pending=True,
                two_factor_pending=True,
                detail="two_factor_required",
            )

        if self._challenge_pending:
            return AccountStatusInfo(
                username=self.username,
                session_valid=False,
                challenge_pending=True,
                two_factor_pending=False,
                detail="challenge_pending",
            )

        if self._session_valid:
            return AccountStatusInfo(
                username=self.username,
                session_valid=True,
                challenge_pending=False,
                detail="session_loaded",
            )

        path = self._session_file()
        if path is None or not path.is_file():
            return AccountStatusInfo(
                username=self.username,
                session_valid=False,
                challenge_pending=False,
                detail="no_session_file",
            )

        # Tenta validar sessão sem re-login com senha.
        from instagrapi.exceptions import ChallengeRequired, LoginRequired

        try:
            self._client.load_settings(str(path))
            self._apply_proxy(self.proxy)
            # account_info exige auth; falha → sessão inválida.
            if hasattr(self._client, "account_info"):
                self._client.account_info()
            self._session_valid = True
            return AccountStatusInfo(
                username=self.username,
                session_valid=True,
                challenge_pending=False,
                detail="session_ok",
            )
        except ChallengeRequired:
            self._challenge_pending = True
            return AccountStatusInfo(
                username=self.username,
                session_valid=False,
                challenge_pending=True,
                detail="challenge_pending",
            )
        except LoginRequired:
            return AccountStatusInfo(
                username=self.username,
                session_valid=False,
                challenge_pending=False,
                detail="login_required",
            )
        except Exception as exc:
            logger.warning("get_account_status falhou (@%s): %s", self.username, type(exc).__name__)
            return AccountStatusInfo(
                username=self.username,
                session_valid=False,
                challenge_pending=False,
                detail=f"error:{type(exc).__name__}",
            )

    def resolve_user_id(self, username: str) -> str | None:
        from instagrapi.exceptions import UserNotFound

        ready_err = self._ensure_session()
        if ready_err:
            logger.warning("resolve_user_id sem sessão: %s", ready_err)
            return None
        handle = username.lstrip("@").strip().lower()
        try:
            uid = self._client.user_id_from_username(handle)
            return str(uid) if uid is not None else None
        except UserNotFound:
            return None
        except Exception:
            logger.exception("resolve_user_id falhou para @%s", handle)
            return None

    # --- handlers / challenge ---

    def _install_noninteractive_handlers(self, *, challenge_code: str | None = None) -> None:
        """Substitui handlers default (stdin) e faz handle_exception re-raise."""

        code_holder = challenge_code if challenge_code is not None else self._pending_challenge_code

        def challenge_code_handler(username: str, choice: Any = None) -> str:
            # Nunca ``input()`` — sob uvicorn bloquearia o event loop / worker.
            _ = username, choice
            if code_holder:
                return str(code_holder)
            logger.warning(
                "challenge_code_handler sem código para @%s — retornando vazio",
                self.username or username,
            )
            return ""

        def change_password_handler(username: str) -> str:
            _ = username
            logger.warning(
                "change_password_handler chamado para @%s — não suportado sem UI",
                self.username or username,
            )
            return ""

        def handle_exception(client: Any, exc: Exception) -> None:
            # Re-raise: evita auto challenge_resolve → stdin.
            _ = client
            raise exc

        self._client.challenge_code_handler = challenge_code_handler
        self._client.change_password_handler = change_password_handler
        self._client.handle_exception = handle_exception

    def _install_challenge_choice_resolver(self) -> None:
        """Honra ``email``/``sms`` em ``select_verify_method`` (instagrapi prefere email)."""
        if self._challenge_choice_resolver_installed:
            return

        adapter = self
        client = self._client
        original_resolve_simple = client.challenge_resolve_simple

        def challenge_resolve_simple_with_choice(challenge_url: str) -> bool:
            from instagrapi.mixins.challenge import ChallengeChoice

            step_name = client.last_json.get("step_name", "")
            if step_name != "select_verify_method":
                return original_resolve_simple(challenge_url)

            pref = adapter._active_challenge_choice
            steps = client.last_json.get("step_data", {}).keys()
            url = challenge_url.lstrip("/")

            if pref == "sms" and "phone_number" in steps:
                choice = ChallengeChoice.SMS
            elif pref == "email" and "email" in steps:
                choice = ChallengeChoice.EMAIL
            elif "email" in steps:
                choice = ChallengeChoice.EMAIL
            elif "phone_number" in steps:
                choice = ChallengeChoice.SMS
            else:
                return original_resolve_simple(challenge_url)

            client._send_private_request(url, {"choice": str(choice.value)})
            code = client.challenge_code_or_raised(choice, wait_seconds=5, attempts=24)
            client._send_private_request(url, {"security_code": code})
            assert client.last_json.get("action", "") == "close"
            assert client.last_json.get("status", "") == "ok"
            return True

        client.challenge_resolve_simple = challenge_resolve_simple_with_choice
        self._challenge_choice_resolver_installed = True

    def _try_challenge_resolve(
        self,
        code: str,
        *,
        choice: ChallengeChoiceStr,
        path: Path | None,
        last_json: dict[str, Any] | None = None,
    ) -> LoginResult:
        """Chama ``challenge_resolve`` com handler que devolve ``code``."""
        _ = code  # já instalado no handler
        self._active_challenge_choice = choice
        payload = last_json if last_json is not None else getattr(self._client, "last_json", None)
        if not isinstance(payload, dict) or not payload:
            self._challenge_pending = True
            self._session_valid = False
            return LoginResult(
                success=False,
                challenge_pending=True,
                detail="missing_challenge_json",
            )

        try:
            ok = bool(self._client.challenge_resolve(payload))
            if not ok:
                self._challenge_pending = True
                self._session_valid = False
                self._dump_session(path)
                self._write_challenge_sidecar(payload)
                return LoginResult(
                    success=False,
                    challenge_pending=True,
                    detail="challenge_resolve_false",
                )
            self._dump_session(path)
            self._clear_challenge_sidecar()
            self._session_valid = True
            self._challenge_pending = False
            self._two_factor_pending = False
            self._pending_challenge_code = None
            logger.info("Challenge resolvido para @%s", self.username)
            return LoginResult(success=True, detail="challenge_resolved")
        except Exception as exc:
            self._challenge_pending = True
            self._session_valid = False
            self._dump_session(path)
            # Atualiza sidecar com last_json mais recente se existir.
            fresh = getattr(self._client, "last_json", None)
            if isinstance(fresh, dict) and fresh:
                self._write_challenge_sidecar(fresh)
            else:
                self._write_challenge_sidecar(payload)
            logger.warning(
                "challenge_resolve falhou (@%s): %s",
                self.username,
                type(exc).__name__,
            )
            return LoginResult(
                success=False,
                challenge_pending=True,
                detail=type(exc).__name__,
            )

    def _persist_challenge_pending(self, exc: Exception, *, detail: str) -> LoginResult:
        path = self._session_file()
        self._challenge_pending = True
        self._two_factor_pending = False
        self._session_valid = False
        self._dump_session(path)
        last_json = getattr(self._client, "last_json", None)
        if isinstance(last_json, dict) and last_json:
            self._write_challenge_sidecar(last_json)
        else:
            # Fallback: tenta serializar atributos úteis da exceção sem secrets.
            fallback = {"message": detail, "exception": type(exc).__name__}
            self._write_challenge_sidecar(fallback)
        logger.warning(
            "ChallengeRequired no login de @%s: %s (sidecar persistido)",
            self.username,
            type(exc).__name__,
        )
        return LoginResult(
            success=False,
            challenge_pending=True,
            detail=detail,
        )

    def _challenge_sidecar_path(self) -> Path | None:
        path = self._session_file()
        if path is None:
            return None
        return Path(f"{path}.challenge.json")

    def _write_challenge_sidecar(self, last_json: dict[str, Any]) -> None:
        sidecar = self._challenge_sidecar_path()
        if sidecar is None:
            return
        try:
            sidecar.parent.mkdir(parents=True, exist_ok=True)
            sidecar.write_text(
                json.dumps(last_json, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        except OSError:
            logger.exception("Falha ao gravar sidecar challenge (sem expor conteúdo)")

    def _clear_challenge_sidecar(self) -> None:
        sidecar = self._challenge_sidecar_path()
        if sidecar is None or not sidecar.is_file():
            return
        try:
            sidecar.unlink()
        except OSError:
            logger.warning("Não foi possível remover sidecar challenge")

    # --- helpers ---

    def _apply_proxy(self, proxy: str | None) -> None:
        if not proxy:
            return
        try:
            self._client.set_proxy(proxy)
        except Exception:
            logger.exception("Falha ao aplicar proxy (sem expor credenciais)")

    def _session_file(self) -> Path | None:
        if not self.session_path:
            return None
        return Path(self.session_path)

    def _dump_session(self, path: Path | None) -> None:
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._client.dump_settings(str(path))
        except Exception:
            logger.warning("dump_settings falhou (@%s)", self.username)

    def _ensure_session(self) -> str | None:
        """Garante cliente com sessão carregada. Retorna mensagem de erro ou None."""
        if self._challenge_pending or self._two_factor_pending:
            return "challenge_pending"
        if self._session_valid:
            return None

        path = self._session_file()
        if path is None or not path.is_file():
            return "no_session"

        from instagrapi.exceptions import ChallengeRequired, LoginRequired

        try:
            self._client.load_settings(str(path))
            self._apply_proxy(self.proxy)
            self._session_valid = True
            return None
        except ChallengeRequired:
            self._challenge_pending = True
            return "challenge_pending"
        except LoginRequired:
            return "login_required"
        except Exception as exc:
            return f"session_load_failed:{type(exc).__name__}"

    def _own_user_id(self) -> int | None:
        raw = getattr(self._client, "user_id", None)
        if raw is None:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _peer_username(thread: Any, own_id: int | None) -> str | None:
        users = getattr(thread, "users", None) or []
        for user in users:
            uid = getattr(user, "pk", None) or getattr(user, "id", None)
            if own_id is not None and uid is not None and int(uid) == int(own_id):
                continue
            uname = getattr(user, "username", None)
            if uname:
                return str(uname).lstrip("@").lower()
        # Fallback: thread com um único peer
        if len(users) == 1:
            uname = getattr(users[0], "username", None)
            if uname:
                return str(uname).lstrip("@").lower()
        return None


def get_instagram_adapter(
    username: str | None = None,
    *,
    session_path: str | None = None,
    proxy: str | None = None,
    adapter: str | None = None,
) -> InstagramAdapter:
    """Factory — default ``stub`` (testes/CI); ``instagrapi`` via settings/env."""
    from config import get_settings

    settings = get_settings()
    kind = (adapter or settings.instagram_adapter or "stub").strip().lower()
    if kind == "instagrapi":
        return InstagrapiAdapter(
            username=username,
            session_path=session_path,
            proxy=proxy,
        )
    return StubInstagramAdapter(
        username=username,
        session_path=session_path,
        proxy=proxy,
    )
