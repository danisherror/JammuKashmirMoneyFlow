import { Suspense, lazy } from 'react'
import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'

// Lazy load routes to reduce initial bundle size
const Overview = lazy(() => import('./pages/Overview'))
const Departments = lazy(() => import('./pages/Departments'))
const DepartmentDetail = lazy(() => import('./pages/DepartmentDetail'))
const Schemes = lazy(() => import('./pages/Schemes'))
const SchemeDetail = lazy(() => import('./pages/SchemeDetail'))
const Districts = lazy(() => import('./pages/Districts'))
const DistrictDetail = lazy(() => import('./pages/DistrictDetail'))
const Alerts = lazy(() => import('./pages/Alerts'))
const SyncStatus = lazy(() => import('./pages/SyncStatus'))
const Export = lazy(() => import('./pages/Export'))
const Tenders = lazy(() => import('./pages/Tenders'))
const DBT = lazy(() => import('./pages/DBT'))

const LoadingFallback = () => (
  <div className="h-full flex items-center justify-center mono text-[10px] text-dim animate-pulse">
    Loading module...
  </div>
)

export default function App() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index              element={<Overview />} />
          <Route path="departments" element={<Departments />} />
          <Route path="departments/:id" element={<DepartmentDetail />} />
          <Route path="schemes"     element={<Schemes />} />
          <Route path="schemes/:id" element={<SchemeDetail />} />
          <Route path="districts"   element={<Districts />} />
          <Route path="districts/:id" element={<DistrictDetail />} />
          <Route path="tenders"     element={<Tenders />} />
          <Route path="dbt"         element={<DBT />} />
          <Route path="alerts"      element={<Alerts />} />
          <Route path="sync"        element={<SyncStatus />} />
          <Route path="export"      element={<Export />} />
        </Route>
      </Routes>
    </Suspense>
  )
}
