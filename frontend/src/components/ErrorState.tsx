interface ErrorStateProps {
  message: string
  onRetry?: () => void
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div
      className="rounded-lg border border-red-200 bg-red-50 px-4 py-6 text-sm text-red-800"
      role="alert"
    >
      <p className="font-medium">Não foi possível carregar os dados</p>
      <p className="mt-1 text-red-700">{message}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded-md bg-red-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-800"
        >
          Tentar novamente
        </button>
      ) : null}
    </div>
  )
}
