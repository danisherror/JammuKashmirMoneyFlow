import { useQuery } from '@tanstack/react-query'
import { TriangleAlert } from 'lucide-react'
import { fetchHealth } from '../lib/api'

/**
 * Site-wide red banner while the API runs with DEMO_MODE=true (todo.md 1.1): the budget
 * allocations it serves are made up (backend/database/demo_data.py). Renders nothing otherwise.
 */
export default function DemoBanner() {
  const { data } = useQuery({ queryKey: ['health'], queryFn: fetchHealth, staleTime: 60_000 })
  if (!data?.demo_mode) return null
  return (
    <div
      role="alert"
      className="flex items-center justify-center gap-2 px-6 py-2 bg-red-600 text-white text-sm font-bold tracking-wide"
    >
      <TriangleAlert size={16} aria-hidden />
      DEMO DATA — NOT REAL. Budget allocations are made up for local development (DEMO_MODE=true).
    </div>
  )
}
