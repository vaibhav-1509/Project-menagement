import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { useChartTheme } from './chartColors'

export default function ComparisonPieChart({ data }) {
  const theme = useChartTheme()
  const hasData = data.some((d) => d.count > 0)

  if (!hasData) {
    return <p className="hint">No completions in this range yet.</p>
  }

  return (
    <ResponsiveContainer width="100%" height={240}>
      <PieChart>
        <Pie data={data} dataKey="count" nameKey="label" innerRadius={50} outerRadius={85} paddingAngle={2}>
          {data.map((entry, i) => (
            <Cell key={entry.label} fill={theme.categorical[i % theme.categorical.length]} stroke="var(--surface)" />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8 }}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
      </PieChart>
    </ResponsiveContainer>
  )
}
