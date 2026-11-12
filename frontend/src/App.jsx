import { useEffect, useState } from 'react'
import './App.css'

const API = '/api'

function App() {
  const [activePage, setActivePage] = useState('Overview')
  const [pods, setPods] = useState([])
  const [issues, setIssues] = useState([])
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function loadData() {
    setLoading(true)
    setError('')

    try {
      const endpoints = ['pods', 'issues', 'events']
      const responses = await Promise.all(
        endpoints.map((endpoint) =>
          fetch(`${API}/${endpoint}`).then((response) => {
            if (!response.ok) throw new Error(`API ${endpoint}: ${response.status}`)
            return response.json()
          }),
        ),
      )

      setPods(Array.isArray(responses[0]) ? responses[0] : [])
      setIssues(Array.isArray(responses[1]) ? responses[1] : [])
      setEvents(Array.isArray(responses[2]) ? responses[2] : [])
    } catch (err) {
      setError(err.message || 'Impossible de contacter OpsPilot API')
    } finally {
      setLoading(false)
    }
  }

useEffect(() => {
  const timer = setTimeout(() => {
    loadData()
  }, 0)

  const interval = setInterval(() => {
    loadData()
  }, 15000)

  return () => {
    clearTimeout(timer)
    clearInterval(interval)
  }
}, [])
  const running = pods.filter((pod) => pod.status === 'Running').length
  const unhealthy = pods.length - running

  const navigation = [
    { name: 'Overview', icon: '◫' },
    { name: 'Pods', icon: '▦' },
    { name: 'Incidents', icon: '⚠' },
    { name: 'Events', icon: '◷' },
    { name: 'Monitoring', icon: '⌁' },
  ]

  function renderContent() {
    if (activePage === 'Pods') {
      return (
        <section className="panel">
          <div className="panel-heading">
            <div><h2>Kubernetes Pods</h2><p>Pods in opspilot-lab namespace</p></div>
            <span className="count">{pods.length} pods</span>
          </div>
          <PodTable pods={pods} />
        </section>
      )
    }

    if (activePage === 'Incidents') {
      return (
        <section className="panel">
          <div className="panel-heading"><div><h2>Active incidents</h2><p>Detected Kubernetes issues</p></div></div>
          {issues.length === 0 ? <EmptyState message="No active incidents detected" /> :
            <div className="event-list">{issues.map((issue, i) => <div className="event" key={i}><span className="status-dot red" /><div><strong>{issue.name || issue.pod_name || 'Kubernetes issue'}</strong><p>{issue.message || issue.reason || JSON.stringify(issue)}</p></div></div>)}</div>}
        </section>
      )
    }

    if (activePage === 'Events') {
      return (
        <section className="panel">
          <div className="panel-heading"><div><h2>Cluster events</h2><p>Recent Kubernetes activity</p></div></div>
          {events.length === 0 ? <EmptyState message="No recent events" /> :
            <div className="event-list">{events.map((event, i) => <div className="event" key={i}><span className="status-dot blue" /><div><strong>{event.reason || event.type || 'Event'}</strong><p>{event.message || event.name || JSON.stringify(event)}</p></div></div>)}</div>}
        </section>
      )
    }

    if (activePage === 'Monitoring') {
      return (
        <section className="panel">
          <div className="panel-heading"><div><h2>Monitoring</h2><p>Prometheus and Grafana metrics</p></div></div>
          <p className="monitoring-text">Detailed infrastructure metrics are available in Grafana.</p>
          <a className="primary-button" href="http://localhost:3000" target="_blank" rel="noreferrer">Open Grafana ↗</a>
        </section>
      )
    }

    return (
      <>
        <div className="stats-grid">
          <StatCard label="Total Pods" value={pods.length} detail="In opspilot-lab" icon="▦" />
          <StatCard label="Running Pods" value={running} detail="Healthy workloads" icon="✓" color="green" />
          <StatCard label="Unhealthy Pods" value={unhealthy} detail="Not running" icon="!" color="orange" />
          <StatCard label="Active Incidents" value={issues.length} detail="Requires attention" icon="⚠" color="red" />
        </div>

        <section className="panel">
          <div className="panel-heading">
            <div><h2>Pods overview</h2><p>Current workload status</p></div>
            <button className="text-button" onClick={() => setActivePage('Pods')}>View all →</button>
          </div>
          <PodTable pods={pods.slice(0, 5)} />
        </section>

        <div className="bottom-grid">
          <section className="panel">
            <div className="panel-heading"><div><h2>Active incidents</h2><p>Issues requiring attention</p></div></div>
            {issues.length === 0 ? <EmptyState message="All systems operational" /> :
              issues.slice(0, 4).map((issue, i) => <div className="event" key={i}><span className="status-dot red" /><div><strong>{issue.name || issue.pod_name || 'Pod issue'}</strong><p>{issue.message || issue.reason || 'Issue detected'}</p></div></div>)}
          </section>
          <section className="panel">
            <div className="panel-heading"><div><h2>Recent events</h2><p>Kubernetes activity</p></div></div>
            {events.length === 0 ? <EmptyState message="No recent events" /> :
              events.slice(0, 4).map((event, i) => <div className="event" key={i}><span className="status-dot blue" /><div><strong>{event.reason || event.type || 'Event'}</strong><p>{event.message || event.name || 'Cluster event'}</p></div></div>)}
          </section>
        </div>
      </>
    )
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-icon">O</div><span>OpsPilot</span></div>
        <div className="nav-label">WORKSPACE</div>
        <nav>
          {navigation.map((item) => (
            <button key={item.name} className={`nav-item ${activePage === item.name ? 'active' : ''}`} onClick={() => setActivePage(item.name)}>
              <span>{item.icon}</span>{item.name}
              {item.name === 'Incidents' && issues.length > 0 && <small>{issues.length}</small>}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer"><span className="status-dot green" /> Cluster: opspilot <small>Connected</small></div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div><span className="breadcrumb">Workspace / </span><strong>{activePage}</strong></div>
          <div className="top-actions"><span className="live-indicator"><span className="status-dot green" /> Live updates</span><button className="refresh-button" onClick={loadData}>↻ Refresh</button></div>
        </header>

        <div className="page-content">
          <div className="page-heading">
            <div><div className="eyebrow">KUBERNETES MANAGEMENT</div><h1>{activePage === 'Overview' ? 'Cluster overview' : activePage}</h1><p>Monitor and manage your Kubernetes infrastructure.</p></div>
            <div className="cluster-tag"><span className="status-dot green" /> opspilot-lab</div>
          </div>

          {error && <div className="error-banner">API connection error: {error}. Check that the FastAPI service is accessible.</div>}
          {loading && pods.length === 0 ? <div className="loading">Loading cluster data...</div> : renderContent()}
          <footer>OpsPilot <span>•</span> Kubernetes Operations Dashboard</footer>
        </div>
      </main>
    </div>
  )
}

function StatCard({ label, value, detail, icon, color = 'blue' }) {
  return <div className="stat-card"><div className={`stat-icon ${color}`}>{icon}</div><div className="stat-label">{label}</div><div className="stat-value">{value}</div><div className="stat-detail">{detail}</div></div>
}

function PodTable({ pods }) {
  const [selectedPod, setSelectedPod] = useState(null)
  const [logs, setLogs] = useState('')
  const [logsLoading, setLogsLoading] = useState(false)
  const [logsError, setLogsError] = useState('')

  async function showLogs(podName) {
    setSelectedPod(podName)
    setLogs('')
    setLogsError('')
    setLogsLoading(true)

    try {
      const response = await fetch(
        `${API}/pods/${encodeURIComponent(podName)}/logs?tail_lines=100`
      )
      if (!response.ok) throw new Error(`HTTP ${response.status}`)

      const data = await response.json()
      const result = Array.isArray(data) ? data[0] : data
      setLogs(typeof result === 'string' ? result : JSON.stringify(result, null, 2))
    } catch (error) {
      setLogsError(error.message || 'Unable to load logs')
    } finally {
      setLogsLoading(false)
    }
  }

  if (pods.length === 0) return <EmptyState message="No pods found" />

  return (
    <>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>Pod name</th><th>Status</th><th>Namespace</th></tr>
          </thead>
          <tbody>
            {pods.map((pod, i) => (
              <tr key={pod.name || i}>
                <td className="pod-name">
                  <button className="pod-link" onClick={() => showLogs(pod.name)}>
                    {pod.name || 'Unknown'}
                  </button>
                </td>
                <td>
                  <span className={`pill ${pod.status === 'Running' ? 'healthy' : 'warning'}`}>
                    <span className="status-dot" />{pod.status || 'Unknown'}
                  </span>
                </td>
                <td>{pod.namespace || 'opspilot-lab'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selectedPod && (
        <section className="logs-panel">
          <div className="panel-heading">
            <div><h2>Pod logs</h2><p>{selectedPod}</p></div>
            <div className="logs-actions">
              <button className="text-button" onClick={() => showLogs(selectedPod)}>↻ Refresh logs</button>
              <button className="text-button" onClick={() => setSelectedPod(null)}>✕ Close</button>
            </div>
          </div>
          {logsLoading ? <p className="loading">Loading logs...</p> :
            logsError ? <div className="error-banner">{logsError}</div> :
              <pre className="logs-content">{logs || 'No logs available.'}</pre>}
        </section>
      )}
    </>
  )
}

function EmptyState({ message }) {
  return <div className="empty-state"><span>✓</span><p>{message}</p></div>
}

export default App
