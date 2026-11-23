import { Link, useParams } from 'react-router-dom'
import { useAppStore } from '../store'
import { fetchGrantBreakdown } from '../lib/api'
import PageHeader from '../components/PageHeader'
import BreakdownSection from '../components/BreakdownSection'
import { ChevronLeft } from 'lucide-react'

/** Breakdown of one CAG grant, including grants not mapped to a tracker department. */
export default function GrantDetail() {
  const { grantNo } = useParams<{ grantNo: string }>()
  const { financialYear } = useAppStore()
  const no = Number(grantNo)

  return (
    <div>
      <PageHeader
        title={`GRANT ${grantNo}`}
        subtitle="CAG APPROPRIATION ACCOUNTS"
        right={
          <Link to="/grants" className="flex items-center gap-1 mono text-[9px] text-dim hover:text-white border px-3 py-1.5 transition-colors"
            style={{ borderColor: '#1a2a3a' }}>
            <ChevronLeft size={12} /> ALL GRANTS
          </Link>
        }
      />
      <div className="p-6">
        <BreakdownSection queryKey={['grant-breakdown', no]} fetch={fy => fetchGrantBreakdown(no, fy)} financialYear={financialYear} />
      </div>
    </div>
  )
}
