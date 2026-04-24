import { NavLink, Outlet } from 'react-router-dom'
import { useAppStore } from '../store'
import {
  LayoutDashboard, Building2, ListChecks,
  MapPin, Bell, Database, ChevronLeft, ChevronRight
} from 'lucide-react'
import clsx from 'clsx'
import DataFreshness from './DataFreshness'

const NAV = [
  { to: '/',            icon: LayoutDashboard, label: 'Overview'    },
  { to: '/departments', icon: Building2,       label: 'Departments' },
  { to: '/schemes',     icon: ListChecks,      label: 'Schemes'     },
  { to: '/districts',   icon: MapPin,          label: 'Districts'   },
  { to: '/alerts',      icon: Bell,            label: 'Alerts'      },
  { to: '/sync',        icon: Database,        label: 'Sync Status' },
]

export default function Layout() {
  const { sidebarOpen, toggleSidebar, financialYear, setFinancialYear } = useAppStore()

  return (
    <div className="flex h-screen overflow-hidden" style={{ position: 'relative', zIndex: 1 }}>

      {/* Sidebar */}
      <aside
        className={clsx(
          'flex flex-col border-r transition-all duration-200 flex-shrink-0',
          sidebarOpen ? 'w-52' : 'w-14'
        )}
        style={{ background: '#080e18', borderColor: '#1a2a3a' }}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 px-3 py-4 border-b" style={{ borderColor: '#1a2a3a' }}>
          <span className="display text-3xl text-gold glow-gold flex-shrink-0">₹</span>
          {sidebarOpen && (
            <div>
              <div className="mono text-xs text-gold tracking-widest">J&K FLOW</div>
              <div className="mono text-[8px] text-dim tracking-widest">PUBLIC MONEY</div>
            </div>
          )}
        </div>

        {/* FY selector */}
        {sidebarOpen && (
          <div className="px-3 py-2 border-b" style={{ borderColor: '#1a2a3a' }}>
            <div className="mono text-[8px] text-dim mb-1 tracking-widest">FISCAL YEAR</div>
            <select
              value={financialYear}
              onChange={e => setFinancialYear(e.target.value)}
              className="w-full mono text-[10px] bg-transparent text-gold border px-2 py-1 outline-none"
              style={{ borderColor: '#1a2a3a' }}
            >
              <option value="2024-25">2024-25</option>
              <option value="2023-24">2023-24</option>
            </select>
          </div>
        )}

        {/* Nav */}
        <nav className="flex-1 py-2">
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2.5 mx-1 my-0.5 transition-all',
                  isActive
                    ? 'bg-green-900/20 border-l-2 border-green-400 text-green'
                    : 'text-dim hover:text-white border-l-2 border-transparent hover:bg-white/5'
                )
              }
            >
              <Icon size={15} className="flex-shrink-0" />
              {sidebarOpen && <span className="mono text-[10px] tracking-widest">{label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* Toggle */}
        <button
          onClick={toggleSidebar}
          className="flex items-center justify-center py-3 border-t text-dim hover:text-white transition-colors"
          style={{ borderColor: '#1a2a3a' }}
        >
          {sidebarOpen ? <ChevronLeft size={14} /> : <ChevronRight size={14} />}
        </button>
      </aside>

      {/* Main content */}
      <div className="flex-1 overflow-auto flex flex-col">
        {/* Data freshness strip — always visible on every page */}
        <DataFreshness />
        <div className="flex-1 overflow-auto">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
