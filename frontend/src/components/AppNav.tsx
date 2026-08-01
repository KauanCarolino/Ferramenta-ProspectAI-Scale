import { Link } from '@tanstack/react-router'
import { cn } from '@/lib/utils'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', exact: true },
  { to: '/campanhas', label: 'Campanhas', exact: false },
  { to: '/leads', label: 'Leads', exact: false },
  { to: '/templates', label: 'Templates', exact: false },
  { to: '/contas', label: 'Contas', exact: false },
  { to: '/logs', label: 'Logs', exact: false },
  { to: '/configuracoes', label: 'Configurações', exact: false },
] as const

const navLinkClass = cn(
  'rounded-md px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900',
)

const navLinkActiveClass = cn(
  'rounded-md px-3 py-1.5 text-sm font-medium bg-brand-100 text-brand-700',
)

export function AppNav() {
  return (
    <nav aria-label="Principal" className="flex flex-wrap gap-1">
      {NAV_ITEMS.map((item) => (
        <Link
          key={item.to}
          to={item.to}
          className={navLinkClass}
          activeProps={{ className: navLinkActiveClass }}
          activeOptions={item.exact ? { exact: true } : undefined}
        >
          {item.label}
        </Link>
      ))}
    </nav>
  )
}
