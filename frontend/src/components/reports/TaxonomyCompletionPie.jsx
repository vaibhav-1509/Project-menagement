import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { useIsDarkMode } from './chartColors'

const GOOD = { light: '#0ca30c', dark: '#0ca30c' }
const REMAINING = { light: '#c3c2b7', dark: '#383835' }

export default function TaxonomyCompletionPie({ item }) {
  const isDark = useIsDarkMode()
  if (!item || item.totalFiles === 0) {
    return <p className="hint">No files in this selection.</p>
  }

  const remaining = item.totalFiles - item.completedFiles
  const data = [
    { label: 'Completed', value: item.completedFiles },
    { label: 'Remaining', value: remaining },
  ].filter((d) => d.value > 0)
  const colors = { Completed: isDark ? GOOD.dark : GOOD.light, Remaining: isDark ? REMAINING.dark : REMAINING.light }

  return (
    <div>
      <div className="taxonomy-progress-header">
        <strong>{item.name}</strong>
        {item.isFullyCompleted && <span className="status-pill active">Fully Completed</span>}
        <span className="hint">
          {item.completedFiles} / {item.totalFiles} files ({item.completionPct}%)
        </span>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="label" innerRadius={45} outerRadius={75} paddingAngle={2}>
            {data.map((entry) => (
              <Cell key={entry.label} fill={colors[entry.label]} stroke="var(--surface)" />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8 }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}
