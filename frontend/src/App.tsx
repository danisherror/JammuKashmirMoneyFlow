import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Overview from './pages/Overview'
import Departments from './pages/Departments'
import DepartmentDetail from './pages/DepartmentDetail'
import Schemes from './pages/Schemes'
import SchemeDetail from './pages/SchemeDetail'
import Districts from './pages/Districts'
import DistrictDetail from './pages/DistrictDetail'
import Alerts from './pages/Alerts'
import SyncStatus from './pages/SyncStatus'
import Export from './pages/Export'
import Tenders from './pages/Tenders'
import DBT from './pages/DBT'

export default function App() {
  return (
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
  )
}
