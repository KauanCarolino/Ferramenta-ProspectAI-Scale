import { useEffect, useId, useState } from 'react'
import { createFileRoute } from '@tanstack/react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { EmptyState } from '@/components/EmptyState'
import { ErrorState } from '@/components/ErrorState'
import { LoadingState } from '@/components/LoadingState'
import { PageHeader } from '@/components/PageHeader'
import {
  createAccount,
  fetchAccounts,
  loginAccount,
  pollInbox,
  refreshAccountStatus,
  resolveAccountChallenge,
  type Account,
  type AccountAuthResponse,
  type ChallengeChoice,
} from '@/lib/api/accounts'
import { getApiErrorMessage } from '@/lib/api/client'
import { cn } from '@/lib/utils'

export const Route = createFileRoute('/contas/')({
  component: AccountsPage,
})

type AuthStep = 'password' | 'challenge' | 'two_factor'
type PendingAuthKind = 'challenge' | 'two_factor'

interface LoginModalProps {
  account: Account | null
  open: boolean
  step: AuthStep
  onStepChange: (step: AuthStep) => void
  onClose: () => void
  onPasswordSubmit: (password: string) => void
  onChallengeSubmit: (code: string, choice: ChallengeChoice) => void
  onTwoFactorSubmit: (password: string, verificationCode: string) => void
  pending: boolean
  error: string | null
  info: string | null
}

function accountStatusClass(status: string): string {
  if (status === 'active' || status === 'ok') {
    return 'bg-emerald-50 text-emerald-800'
  }
  if (status === 'challenge' || status === 'warmup') {
    return 'bg-amber-50 text-amber-900'
  }
  if (status === 'banned' || status === 'error' || status === 'inactive') {
    return 'bg-red-50 text-red-800'
  }
  return 'bg-slate-100 text-slate-700'
}

function isAuthSuccess(result: AccountAuthResponse): boolean {
  if (result.challenge_pending || result.two_factor_pending) return false
  return result.status === 'active' || result.status === 'ok'
}

function authPendingMessage(result: AccountAuthResponse): string {
  if (result.challenge_pending) {
    return 'Instagram pediu verificação. Informe o código enviado por e-mail/SMS.'
  }
  if (result.two_factor_pending) {
    return 'Autenticação em dois fatores necessária. Informe o código 2FA.'
  }
  return 'Aguardando confirmação do Instagram.'
}

function LoginModal({
  account,
  open,
  step,
  onStepChange,
  onClose,
  onPasswordSubmit,
  onChallengeSubmit,
  onTwoFactorSubmit,
  pending,
  error,
  info,
}: LoginModalProps) {
  const passwordId = useId()
  const challengeCodeId = useId()
  const twoFactorCodeId = useId()
  const choiceEmailId = useId()
  const choiceSmsId = useId()

  const [password, setPassword] = useState('')
  const [challengeCode, setChallengeCode] = useState('')
  const [challengeChoice, setChallengeChoice] =
    useState<ChallengeChoice>('email')
  const [twoFactorCode, setTwoFactorCode] = useState('')

  useEffect(() => {
    if (!open) {
      setPassword('')
      setChallengeCode('')
      setChallengeChoice('email')
      setTwoFactorCode('')
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.preventDefault()
        setPassword('')
        setChallengeCode('')
        setChallengeChoice('email')
        setTwoFactorCode('')
        onClose()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  if (!open || !account) return null

  function handleClose() {
    setPassword('')
    setChallengeCode('')
    setChallengeChoice('email')
    setTwoFactorCode('')
    onClose()
  }

  const title =
    step === 'challenge'
      ? `Verificação — @${account.username}`
      : step === 'two_factor'
        ? `2FA — @${account.username}`
        : `Login — @${account.username}`

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/40 p-4 sm:items-center"
      role="presentation"
      onClick={handleClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="login-dialog-title"
        aria-describedby="login-dialog-desc"
        className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-4 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <h2
          id="login-dialog-title"
          className="text-lg font-semibold text-slate-900"
        >
          {title}
        </h2>

        {step === 'password' ? (
          <>
            <p id="login-dialog-desc" className="mt-1 text-sm text-slate-500">
              A senha é usada só nesta chamada e não é armazenada.
            </p>
            <form
              className="mt-4 space-y-4"
              onSubmit={(e) => {
                e.preventDefault()
                onPasswordSubmit(password)
              }}
            >
              <div>
                <label
                  htmlFor={passwordId}
                  className="block text-sm font-medium text-slate-700"
                >
                  Senha
                </label>
                <input
                  id={passwordId}
                  type="password"
                  autoComplete="current-password"
                  autoFocus
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                />
              </div>
              {info ? (
                <p className="text-sm text-amber-800" role="status">
                  {info}
                </p>
              ) : null}
              {error ? (
                <p className="text-sm text-red-600" role="alert">
                  {error}
                </p>
              ) : null}
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={handleClose}
                  className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={pending || !password}
                  className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
                >
                  {pending ? 'Entrando…' : 'Entrar'}
                </button>
              </div>
            </form>
          </>
        ) : null}

        {step === 'challenge' ? (
          <>
            <p id="login-dialog-desc" className="mt-1 text-sm text-slate-500">
              Instagram pediu verificação. Informe o código enviado por
              e-mail/SMS.
            </p>
            <form
              className="mt-4 space-y-4"
              onSubmit={(e) => {
                e.preventDefault()
                onChallengeSubmit(challengeCode.trim(), challengeChoice)
              }}
            >
              <fieldset>
                <legend className="block text-sm font-medium text-slate-700">
                  Canal do código
                </legend>
                <div className="mt-2 flex gap-4">
                  <label
                    htmlFor={choiceEmailId}
                    className="inline-flex items-center gap-2 text-sm text-slate-700"
                  >
                    <input
                      id={choiceEmailId}
                      type="radio"
                      name="challenge-choice"
                      value="email"
                      checked={challengeChoice === 'email'}
                      onChange={() => setChallengeChoice('email')}
                      className="border-slate-300 text-brand-600 focus:ring-brand-500"
                    />
                    E-mail
                  </label>
                  <label
                    htmlFor={choiceSmsId}
                    className="inline-flex items-center gap-2 text-sm text-slate-700"
                  >
                    <input
                      id={choiceSmsId}
                      type="radio"
                      name="challenge-choice"
                      value="sms"
                      checked={challengeChoice === 'sms'}
                      onChange={() => setChallengeChoice('sms')}
                      className="border-slate-300 text-brand-600 focus:ring-brand-500"
                    />
                    SMS
                  </label>
                </div>
              </fieldset>
              <div>
                <label
                  htmlFor={challengeCodeId}
                  className="block text-sm font-medium text-slate-700"
                >
                  Código de verificação
                </label>
                <input
                  id={challengeCodeId}
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  autoFocus
                  required
                  value={challengeCode}
                  onChange={(e) => setChallengeCode(e.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                />
              </div>
              {info ? (
                <p className="text-sm text-amber-800" role="status">
                  {info}
                </p>
              ) : null}
              {error ? (
                <p className="text-sm text-red-600" role="alert">
                  {error}
                </p>
              ) : null}
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <button
                  type="button"
                  onClick={() => {
                    setChallengeCode('')
                    onStepChange('password')
                  }}
                  className="text-left text-sm font-medium text-brand-700 hover:text-brand-800"
                >
                  Usar senha de novo
                </button>
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={handleClose}
                    className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    disabled={pending || !challengeCode.trim()}
                    className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
                  >
                    {pending ? 'Enviando…' : 'Confirmar código'}
                  </button>
                </div>
              </div>
            </form>
          </>
        ) : null}

        {step === 'two_factor' ? (
          <>
            <p id="login-dialog-desc" className="mt-1 text-sm text-slate-500">
              Autenticação em dois fatores necessária. Informe o código do
              aplicativo autenticador ou SMS.
            </p>
            <form
              className="mt-4 space-y-4"
              onSubmit={(e) => {
                e.preventDefault()
                if (!password.trim()) {
                  onStepChange('password')
                  return
                }
                onTwoFactorSubmit(password, twoFactorCode.trim())
              }}
            >
              {!password.trim() ? (
                <p className="text-sm text-amber-800" role="status">
                  A senha desta sessão não está disponível. Volte e entre de
                  novo com a senha para concluir o 2FA.
                </p>
              ) : (
                <div>
                  <label
                    htmlFor={twoFactorCodeId}
                    className="block text-sm font-medium text-slate-700"
                  >
                    Código 2FA
                  </label>
                  <input
                    id={twoFactorCodeId}
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    autoFocus
                    required
                    value={twoFactorCode}
                    onChange={(e) => setTwoFactorCode(e.target.value)}
                    className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  />
                </div>
              )}
              {info ? (
                <p className="text-sm text-amber-800" role="status">
                  {info}
                </p>
              ) : null}
              {error ? (
                <p className="text-sm text-red-600" role="alert">
                  {error}
                </p>
              ) : null}
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <button
                  type="button"
                  onClick={() => {
                    setTwoFactorCode('')
                    onStepChange('password')
                  }}
                  className="text-left text-sm font-medium text-brand-700 hover:text-brand-800"
                >
                  Voltar à senha
                </button>
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={handleClose}
                    className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    disabled={
                      pending ||
                      !password.trim() ||
                      !twoFactorCode.trim()
                    }
                    className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
                  >
                    {pending ? 'Verificando…' : 'Confirmar 2FA'}
                  </button>
                </div>
              </div>
            </form>
          </>
        ) : null}
      </div>
    </div>
  )
}

interface AccountRowProps {
  account: Account
  onLogin: (account: Account) => void
  onResolveChallenge: (account: Account) => void
  feedback: string | null
  pendingKind?: PendingAuthKind
}

function AccountRow({
  account,
  onLogin,
  onResolveChallenge,
  feedback,
  pendingKind,
}: AccountRowProps) {
  const queryClient = useQueryClient()

  const refreshMutation = useMutation({
    mutationFn: () => refreshAccountStatus(account.id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['accounts'] })
    },
  })

  const pollMutation = useMutation({
    mutationFn: () => pollInbox(account.id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['accounts'] })
      await queryClient.invalidateQueries({ queryKey: ['dashboard', 'summary'] })
    },
  })

  const rowError = refreshMutation.error ?? pollMutation.error
  const rowSuccess =
    (refreshMutation.isSuccess && !refreshMutation.isPending) ||
    (pollMutation.isSuccess && !pollMutation.isPending)
  const needsChallenge = account.status === 'challenge'

  return (
    <li className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-medium text-slate-900">@{account.username}</p>
          <span
            className={cn(
              'inline-flex rounded-md px-2 py-0.5 text-xs font-medium',
              accountStatusClass(account.status),
            )}
          >
            {account.status}
          </span>
        </div>
        <p className="text-xs text-slate-500">
          Warm-up dia {account.warmup_day}
          {account.proxy ? ` · Proxy: ${account.proxy}` : ''}
        </p>
        {feedback ? (
          <p
            className={cn(
              'text-xs',
              feedback.startsWith('Login') || feedback.includes('sucesso')
                ? 'text-emerald-700'
                : 'text-amber-800',
            )}
            role="status"
          >
            {feedback}
          </p>
        ) : null}
        {rowError ? (
          <p className="text-xs text-red-600" role="alert">
            {getApiErrorMessage(rowError, 'Falha na ação')}
          </p>
        ) : null}
        {rowSuccess && !rowError ? (
          <p className="text-xs text-emerald-700" role="status">
            {pollMutation.isSuccess && !pollMutation.isPending
              ? `Inbox: ${pollMutation.data?.replies_seen ?? 0} respostas, ${pollMutation.data?.leads_matched ?? 0} leads`
              : 'Status atualizado.'}
          </p>
        ) : null}
      </div>
      <div className="flex flex-wrap gap-2">
        {needsChallenge ? (
          <button
            type="button"
            onClick={() => onResolveChallenge(account)}
            className="rounded-md bg-amber-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-amber-700"
          >
            {pendingKind === 'two_factor'
              ? 'Resolver 2FA'
              : 'Resolver challenge'}
          </button>
        ) : null}
        <button
          type="button"
          onClick={() => onLogin(account)}
          className="rounded-md bg-brand-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-brand-700"
        >
          Login
        </button>
        <button
          type="button"
          disabled={refreshMutation.isPending}
          onClick={() => {
            refreshMutation.reset()
            refreshMutation.mutate()
          }}
          className="rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          {refreshMutation.isPending ? 'Atualizando…' : 'Refresh status'}
        </button>
        <button
          type="button"
          disabled={pollMutation.isPending}
          onClick={() => {
            pollMutation.reset()
            pollMutation.mutate()
          }}
          className="rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          {pollMutation.isPending ? 'Polling…' : 'Inbox poll'}
        </button>
      </div>
    </li>
  )
}

function AccountsPage() {
  const queryClient = useQueryClient()
  const usernameId = useId()
  const proxyId = useId()

  const [username, setUsername] = useState('')
  const [proxy, setProxy] = useState('')
  const [formFeedback, setFormFeedback] = useState<string | null>(null)
  const [loginTarget, setLoginTarget] = useState<Account | null>(null)
  const [authStep, setAuthStep] = useState<AuthStep>('password')
  const [authInfo, setAuthInfo] = useState<string | null>(null)
  const [loginFeedbackById, setLoginFeedbackById] = useState<
    Record<string, string>
  >({})
  const [pendingById, setPendingById] = useState<
    Record<string, PendingAuthKind>
  >({})

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['accounts'],
    queryFn: fetchAccounts,
    retry: 1,
  })

  const createMutation = useMutation({
    mutationFn: () =>
      createAccount({
        username: username.trim(),
        proxy: proxy.trim() || null,
      }),
    onSuccess: async () => {
      setUsername('')
      setProxy('')
      setFormFeedback('Conta adicionada.')
      await queryClient.invalidateQueries({ queryKey: ['accounts'] })
    },
  })

  function clearPending(id: string) {
    setPendingById((prev) => {
      if (!(id in prev)) return prev
      const next = { ...prev }
      delete next[id]
      return next
    })
  }

  function handleAuthResult(result: AccountAuthResponse) {
    if (isAuthSuccess(result)) {
      clearPending(result.id)
      setLoginFeedbackById((prev) => ({
        ...prev,
        [result.id]: 'Login realizado com sucesso.',
      }))
      setLoginTarget(null)
      setAuthStep('password')
      setAuthInfo(null)
      void queryClient.invalidateQueries({ queryKey: ['accounts'] })
      return
    }

    if (result.challenge_pending) {
      setPendingById((prev) => ({ ...prev, [result.id]: 'challenge' }))
      setAuthStep('challenge')
      setAuthInfo(authPendingMessage(result))
      setLoginFeedbackById((prev) => ({
        ...prev,
        [result.id]: 'Challenge pendente — informe o código de verificação.',
      }))
      void queryClient.invalidateQueries({ queryKey: ['accounts'] })
      return
    }

    if (result.two_factor_pending) {
      setPendingById((prev) => ({ ...prev, [result.id]: 'two_factor' }))
      setAuthStep('two_factor')
      setAuthInfo(authPendingMessage(result))
      setLoginFeedbackById((prev) => ({
        ...prev,
        [result.id]: '2FA pendente — informe o código de autenticação.',
      }))
      void queryClient.invalidateQueries({ queryKey: ['accounts'] })
      return
    }

    clearPending(result.id)
    setLoginFeedbackById((prev) => ({
      ...prev,
      [result.id]: `Status atual: ${result.status}.`,
    }))
    setLoginTarget(null)
    setAuthStep('password')
    setAuthInfo(null)
    void queryClient.invalidateQueries({ queryKey: ['accounts'] })
  }

  const loginMutation = useMutation({
    mutationFn: ({
      id,
      password,
      verification_code,
    }: {
      id: string
      password: string
      verification_code?: string
    }) =>
      loginAccount(id, {
        password,
        ...(verification_code ? { verification_code } : {}),
      }),
    onSuccess: (result) => {
      handleAuthResult(result)
    },
  })

  const challengeMutation = useMutation({
    mutationFn: ({
      id,
      code,
      choice,
    }: {
      id: string
      code: string
      choice: ChallengeChoice
    }) => resolveAccountChallenge(id, { code, choice }),
    onSuccess: (result) => {
      handleAuthResult(result)
    },
  })

  const authPending =
    loginMutation.isPending || challengeMutation.isPending
  const authError =
    loginMutation.isError || challengeMutation.isError
      ? getApiErrorMessage(
          loginMutation.error ?? challengeMutation.error,
          authStep === 'challenge'
            ? 'Falha ao resolver challenge'
            : authStep === 'two_factor'
              ? 'Falha na verificação 2FA'
              : 'Falha no login',
        )
      : null

  function openAuthModal(account: Account, step: AuthStep, info?: string | null) {
    loginMutation.reset()
    challengeMutation.reset()
    setAuthInfo(info ?? null)
    setAuthStep(step)
    setLoginTarget(account)
  }

  function openResolvePending(account: Account) {
    if (pendingById[account.id] === 'two_factor') {
      openAuthModal(
        account,
        'password',
        '2FA pendente. A senha não permanece após fechar o modal — informe a senha e, em seguida, o código 2FA.',
      )
      return
    }
    // challenge conhecido ou status=challenge sem mapa (ex.: pós-refresh) → POST /challenge
    openAuthModal(
      account,
      'challenge',
      'Instagram pediu verificação. Informe o código enviado por e-mail/SMS.',
    )
  }

  function closeAuthModal() {
    setLoginTarget(null)
    setAuthStep('password')
    setAuthInfo(null)
    loginMutation.reset()
    challengeMutation.reset()
  }

  return (
    <>
      <PageHeader
        title="Contas"
        description="Contas Instagram — login, status e proxy"
      />

      <section
        aria-label="Adicionar conta"
        className="mb-6 rounded-lg border border-slate-200 bg-white p-4"
      >
        <h2 className="text-sm font-semibold text-slate-900">Adicionar conta</h2>
        <form
          className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-end"
          onSubmit={(e) => {
            e.preventDefault()
            setFormFeedback(null)
            createMutation.reset()
            createMutation.mutate()
          }}
        >
          <div className="min-w-0 flex-1">
            <label
              htmlFor={usernameId}
              className="block text-sm font-medium text-slate-700"
            >
              Username
            </label>
            <input
              id={usernameId}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              placeholder="minha_conta"
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
          </div>
          <div className="min-w-0 flex-1">
            <label
              htmlFor={proxyId}
              className="block text-sm font-medium text-slate-700"
            >
              Proxy (opcional)
            </label>
            <input
              id={proxyId}
              value={proxy}
              onChange={(e) => setProxy(e.target.value)}
              placeholder="http://user:pass@host:port"
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
          </div>
          <button
            type="submit"
            disabled={createMutation.isPending || !username.trim()}
            className="rounded-md bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {createMutation.isPending ? 'Salvando…' : 'Adicionar'}
          </button>
        </form>
        {createMutation.isError ? (
          <p className="mt-2 text-sm text-red-600" role="alert">
            {getApiErrorMessage(createMutation.error, 'Falha ao criar conta')}
          </p>
        ) : null}
        {formFeedback ? (
          <p className="mt-2 text-sm text-emerald-700" role="status">
            {formFeedback}
          </p>
        ) : null}
      </section>

      {isLoading ? <LoadingState /> : null}

      {isError ? (
        <ErrorState
          message={getApiErrorMessage(error, 'Falha ao carregar contas')}
          onRetry={() => {
            void refetch()
          }}
        />
      ) : null}

      {!isLoading && !isError && (data?.length ?? 0) === 0 ? (
        <EmptyState
          title="Nenhuma conta configurada"
          description="Adicione uma conta acima ou via CLI."
        />
      ) : null}

      {!isLoading && !isError && data && data.length > 0 ? (
        <ul className="divide-y divide-slate-200 overflow-hidden rounded-lg border border-slate-200 bg-white">
          {data.map((account) => (
            <AccountRow
              key={account.id}
              account={account}
              onLogin={(acc) => openAuthModal(acc, 'password')}
              onResolveChallenge={openResolvePending}
              feedback={loginFeedbackById[account.id] ?? null}
              pendingKind={pendingById[account.id]}
            />
          ))}
        </ul>
      ) : null}

      <LoginModal
        account={loginTarget}
        open={Boolean(loginTarget)}
        step={authStep}
        onStepChange={(step) => {
          loginMutation.reset()
          challengeMutation.reset()
          setAuthInfo(null)
          setAuthStep(step)
        }}
        pending={authPending}
        error={authError}
        info={authInfo}
        onClose={closeAuthModal}
        onPasswordSubmit={(password) => {
          if (!loginTarget) return
          loginMutation.mutate({ id: loginTarget.id, password })
        }}
        onChallengeSubmit={(code, choice) => {
          if (!loginTarget) return
          challengeMutation.mutate({
            id: loginTarget.id,
            code,
            choice,
          })
        }}
        onTwoFactorSubmit={(password, verificationCode) => {
          if (!loginTarget) return
          loginMutation.mutate({
            id: loginTarget.id,
            password,
            verification_code: verificationCode,
          })
        }}
      />
    </>
  )
}
