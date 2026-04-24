import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AppState {
  financialYear: string
  setFinancialYear: (fy: string) => void
  sidebarOpen: boolean
  toggleSidebar: () => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      financialYear: '2024-25',
      setFinancialYear: (fy) => set({ financialYear: fy }),
      sidebarOpen: true,
      toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
    }),
    {
      name: 'jk-money-flow-store',
      // Only persist the FY selection — sidebar state resets on each session
      partialize: (state) => ({ financialYear: state.financialYear }),
    }
  )
)
