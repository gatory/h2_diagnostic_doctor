// Side panel (right 60% of the screen) with a few headline numbers. Sample values for now.

const SAMPLE_METRICS = [
  { label: 'Battery', value: '82 %' },
  { label: 'Motor temp', value: '41 °C' },
  { label: 'Joints', value: '30 / 30' },
  { label: 'Topics', value: '6 / 6' },
  { label: 'IMU', value: 'Level' },
]

export function MetricsPanel({ open }: { open: boolean }) {
  return (
    <section className={`metrics-panel ${open ? 'open' : ''}`} aria-hidden={!open}>
      <h2>Metrics</h2>
      <div className="metric-grid">
        {SAMPLE_METRICS.map((m) => (
          <div key={m.label} className="metric">
            <div className="metric-label">{m.label}</div>
            <div className="metric-value">{m.value}</div>
          </div>
        ))}
      </div>
    </section>
  )
}
