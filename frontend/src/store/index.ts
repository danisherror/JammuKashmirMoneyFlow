import { create } from 'zustand'

interface AppState {
  financialYear: string
  setFinancialYear: (fy: string) => void
  sidebarOpen: boolean
  toggleSidebar: () => void
}

export const useAppStore = create<AppState>((set) => ({
  financialYear: '2024-25',
  setFinancialYear: (fy) => set({ financialYear: fy }),
  sidebarOpen: true,
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
}))
