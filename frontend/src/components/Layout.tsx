import { NavLink, Outlet } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { useAppStore } from '../store'
import {
  LayoutDashboard, Building2, ListChecks,
  MapPin, Bell, Database, ChevronLeft, ChevronRight, Download,
  FileText, Wallet, Loader2, Landmark
} from 'lucide-react'
import clsx from 'clsx'
import DataFreshness from './DataFreshness'
import DemoBanner from './DemoBanner'
import ViewSwitch from './ViewSwitch'
import { fetchBudgetOverview, triggerAllCollectors } from '../lib/api'
import toast, { Toaster } from 'react-hot-toast'

const NAV = [
  { to: '/',            icon: LayoutDashboard, label: 'Overview'    },
  { to: '/departments', icon: Building2,       label: 'Departments' },
  { to: '/grants',      icon: Landmark,        label: 'CAG Grants'  },
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
  const [isSyncing, setIsSyncing] = useState(false)

  // Auto-fetch historical data if it is missing
  useEffect(() => {
    let mounted = true
    
    const checkAndSyncData = async () => {
      try {
        const overview = await fetchBudgetOverview(financialYear)
        // No total (null) means no data for this year yet
        if (mounted && overview && (overview.total_budget_lakhs == null || overview.total_budget_lakhs === 0)) {
          setIsSyncing(true)
          toast.loading(`Data for ${financialYear} missing. Starting background sync...`, { id: 'sync-toast' })
          
          await triggerAllCollectors(financialYear)
          
          toast.success(`Government portals are now being scraped for ${financialYear}. Data will populate shortly!`, { 
            id: 'sync-toast', 
            duration: 5000 
          })
          setIsSyncing(false)
        }
      } catch (e) {
        console.error('Failed to check overview data:', e)
        if (mounted) setIsSyncing(false)
      }
    }
    
    checkAndSyncData()
    
    return () => { mounted = false }
  }, [financialYear])

  // Generate financial years from current year down to 1947
  const currentYear = new Date().getFullYear()
  const startYear = 1947
  const financialYears = []
  for (let i = currentYear; i >= startYear; i--) {
    const nextYear = (i + 1).toString().slice(-2)
    financialYears.push(`${i}-${nextYear}`)
  }

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
              {financialYears.map(fy => (
                <option key={fy} value={fy}>{fy}</option>
              ))}
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
      <div className="flex-1 overflow-auto flex flex-col relative">
        <DemoBanner />
        <Toaster position="top-right" toastOptions={{
          style: {
            background: '#0f172a',
            color: '#fff',
            border: '1px solid var(--panel-border)',
          }
        }} />
        
        {/* Sync overlay */}
        {isSyncing && (
          <div className="absolute inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center pointer-events-none">
            <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 flex flex-col items-center shadow-2xl">
              <Loader2 className="w-10 h-10 text-blue-500 animate-spin mb-4" />
              <h3 className="text-lg font-bold text-white mb-2">Connecting to Govt Portals</h3>
              <p className="text-sm text-slate-400">Scraping data for {financialYear}...</p>
            </div>
          </div>
        )}

        {/* Live / Official / Combined switch — kept in the URL (todo.md 2.2a) */}
        <div className="flex items-center px-6 py-2.5 border-b border-slate-700/50 bg-slate-900/40 backdrop-blur-md">
          <ViewSwitch />
        </div>

        {/* Data freshness strip — always visible on every page */}
        <DataFreshness />
        <div className="flex-1 overflow-auto">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
