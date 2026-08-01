interface LoadingStateProps {
  label?: string
}

export function LoadingState({ label = 'Carregando…' }: LoadingStateProps) {
  return (
    <div
      className="flex items-center justify-center rounded-lg border border-dashed border-slate-200 bg-white px-4 py-12 text-sm text-slate-500"
      role="status"
      aria-live="polite"
    >
      {label}
    </div>
  )
}
