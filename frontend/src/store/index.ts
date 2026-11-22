import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { View } from '../lib/api'
import { parseView } from '../lib/sources'

interface AppState {
  financialYear: string
  setFinancialYear: (fy: string) => void
  /**
   * Live / Official / Combined (todo.md 2.2a). The URL's `?view=` is the source of truth;
   * `ViewSwitch` keeps this in sync with it so links can be shared. Not persisted.
   */
  view: View
  setView: (view: View) => void
  sidebarOpen: boolean
  toggleSidebar: () => void
}

// Read the view from the first URL so a shared link doesn't fetch the default view first.
const initialView = (): View =>
  typeof window === 'undefined' ? 'combined' : parseView(new URLSearchParams(window.location.search).get('view'))

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      financialYear: '2024-25',
      setFinancialYear: (fy) => set({ financialYear: fy }),
      view: initialView(),
      setView: (view) => set({ view }),
      sidebarOpen: true,
      toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
    }),
    {
      name: 'jk-money-flow-store',
      // Only persist the FY selection — sidebar state resets on each session, the view lives in the URL
      partialize: (state) => ({ financialYear: state.financialYear }),
    }
  )
)
