import { Outlet, NavLink } from 'react-router-dom'
import { LayoutDashboard, Bell, ShieldCheck, FileText, MessageSquare } from 'lucide-react'
import clsx from 'clsx'

const nav = [
  { to: '/',        label: 'Dashboard',   icon: LayoutDashboard },
  { to: '/alerts',  label: 'Alerts',      icon: Bell },
  { to: '/changes', label: 'Change Risk', icon: ShieldCheck },
  { to: '/reports', label: 'Reports',     icon: FileText },
  { to: '/chat',    label: 'ChatOps',     icon: MessageSquare },
]

export default function Layout() {
  return (
    <div className="flex h-screen">
      <aside className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col">
        <div className="px-5 py-4 border-b border-gray-800">
          <p className="text-xs text-gray-500 font-medium uppercase tracking-widest">AIOps</p>
          <p className="text-sm font-semibold text-white mt-0.5">VCF Platform</p>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {nav.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} end={to === '/'}
              className={({ isActive }) => clsx(
                'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors',
                isActive
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-400 hover:text-white hover:bg-gray-800'
              )}>
              <Icon size={16} />{label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-gray-800 text-xs text-gray-600">v0.1.0</div>
      </aside>
      <main className="flex-1 overflow-auto"><Outlet /></main>
    </div>
  )
}
