import { NavLink, Outlet } from 'react-router-dom'
import { useAppStore } from '../store'
import {
  LayoutDashboard, Building2, ListChecks,
  MapPin, Bell, Database, ChevronLeft, ChevronRight, Download,
  FileText, Wallet
} from 'lucide-react'
import clsx from 'clsx'
import DataFreshness from './DataFreshness'

const NAV = [
  { to: '/',            icon: LayoutDashboard, label: 'Overview'    },
  { to: '/departments', icon: Building2,       label: 'Departments' },
  { to: '/schemes',     icon: ListChecks,      label: 'Schemes'     },
  { to: '/districts',   icon: MapPin,          label: 'Districts'   },
  { to: '/tenders',     icon: FileText,        label: 'Tenders'     },
  { to: '/dbt',         icon: Wallet,          label: 'DBT Flow'    },
  { to: '/alerts',      icon: Bell,            label: 'Alerts'      },
  { to: '/export',      icon: Download,        label: 'Export'      },
  { to: '/sync',        icon: Database,        label: 'Sync Status' },
]

export default function Layout() {
  const { sidebarOpen, toggleSidebar, financialYear, setFinancialYear } = useAppStore()

  return (
    <div className="flex h-screen overflow-hidden" style={{ position: 'relative', zIndex: 1 }}>

      {/* Sidebar */}
      <aside
        className={clsx(
          'flex flex-col transition-all duration-300 flex-shrink-0 z-10',
          sidebarOpen ? 'w-64' : 'w-20'
        )}
        style={{ 
          background: 'rgba(15, 23, 42, 0.4)', 
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          borderRight: '1px solid var(--panel-border)' 
        }}
      >
        {/* Logo */}
        <div className="flex items-center gap-4 px-5 py-6 border-b" style={{ borderColor: 'var(--panel-border)' }}>
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-lg shadow-blue-500/20 flex-shrink-0">
            <span className="text-white font-bold text-xl">₹</span>
          </div>
          {sidebarOpen && (
            <div className="overflow-hidden">
              <div className="display text-xl text-white tracking-wide truncate">J&K FLOW</div>
              <div className="text-[10px] text-blue-400 font-semibold tracking-widest uppercase">Public Money</div>
            </div>
          )}
        </div>

        {/* FY selector */}
        {sidebarOpen && (
          <div className="px-5 py-4 border-b" style={{ borderColor: 'var(--panel-border)' }}>
            <div className="text-[10px] text-slate-400 font-semibold mb-2 tracking-widest uppercase">Fiscal Year</div>
            <select
              value={financialYear}
              onChange={e => setFinancialYear(e.target.value)}
              className="w-full bg-slate-800/50 text-white border border-slate-700/50 rounded-lg px-3 py-2 outline-none focus:border-blue-500/50 transition-colors cursor-pointer"
            >
              <option value="2024-25">2024-25</option>
              <option value="2023-24">2023-24</option>
            </select>
          </div>
        )}

        {/* Nav */}
        <nav className="flex-1 py-4 overflow-y-auto px-3 space-y-1">
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-3 rounded-xl transition-all duration-200 group',
                  isActive
                    ? 'bg-blue-500/10 text-blue-400 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.1)]'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
                )
              }
            >
              <Icon size={20} className={clsx("flex-shrink-0 transition-transform group-hover:scale-110")} />
              {sidebarOpen && <span className="font-medium text-sm tracking-wide">{label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* Toggle */}
        <button
          onClick={toggleSidebar}
          className="flex items-center justify-center py-4 border-t text-slate-400 hover:text-white hover:bg-slate-800/50 transition-colors"
          style={{ borderColor: 'var(--panel-border)' }}
        >
          {sidebarOpen ? <ChevronLeft size={18} /> : <ChevronRight size={18} />}
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
