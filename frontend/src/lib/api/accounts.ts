import { apiFetch } from './client'

export interface Account {
  id: string
  username: string
  status: string
  proxy: string | null
  warmup_day: number
  session_path: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface AccountAuthResponse extends Account {
  login_detail: string | null
  challenge_pending: boolean
  two_factor_pending: boolean
}

export type ChallengeChoice = 'email' | 'sms'

export interface AccountLoginPayload {
  password: string
  verification_code?: string
  challenge_code?: string
  challenge_choice?: ChallengeChoice
}

export interface AccountChallengePayload {
  code: string
  choice?: ChallengeChoice
}

export interface AccountCreatePayload {
  username: string
  proxy?: string | null
  notes?: string | null
  password?: string | null
}

export interface InboxPollResult {
  accounts_polled: number
  replies_seen: number
  leads_matched: number
  errors: number
}

export async function fetchAccounts(): Promise<Account[]> {
  return apiFetch<Account[]>('/accounts')
}

export async function createAccount(
  payload: AccountCreatePayload,
): Promise<Account> {
  return apiFetch<Account>('/accounts', {
    method: 'POST',
    body: payload,
  })
}

export async function loginAccount(
  id: string,
  payload: AccountLoginPayload,
): Promise<AccountAuthResponse> {
  return apiFetch<AccountAuthResponse>(`/accounts/${id}/login`, {
    method: 'POST',
    body: payload,
  })
}

export async function resolveAccountChallenge(
  id: string,
  payload: AccountChallengePayload,
): Promise<AccountAuthResponse> {
  return apiFetch<AccountAuthResponse>(`/accounts/${id}/challenge`, {
    method: 'POST',
    body: payload,
  })
}

export async function refreshAccountStatus(id: string): Promise<Account> {
  return apiFetch<Account>(`/accounts/${id}/refresh-status`, {
    method: 'POST',
  })
}

export async function pollInbox(
  accountId?: string,
): Promise<InboxPollResult> {
  const search = new URLSearchParams()
  if (accountId) {
    search.set('account_id', accountId)
  }
  const query = search.toString()
  return apiFetch<InboxPollResult>(
    `/accounts/inbox-poll${query ? `?${query}` : ''}`,
    { method: 'POST' },
  )
}
