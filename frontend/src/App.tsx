import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Alerts from './pages/Alerts'
import ChangeRisk from './pages/ChangeRisk'
import Reports from './pages/Reports'
import ChatOps from './pages/ChatOps'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="alerts" element={<Alerts />} />
          <Route path="changes" element={<ChangeRisk />} />
          <Route path="reports" element={<Reports />} />
          <Route path="chat" element={<ChatOps />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
