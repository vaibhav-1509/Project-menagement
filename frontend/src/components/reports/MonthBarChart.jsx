import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useChartTheme } from './chartColors'

export default function MonthBarChart({ data }) {
  const theme = useChartTheme()
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke={theme.grid} />
        <XAxis
          dataKey="label"
          stroke={theme.muted}
          tickLine={false}
          axisLine={{ stroke: theme.grid }}
          interval="preserveStartEnd"
          minTickGap={12}
        />
        <YAxis allowDecimals={false} stroke={theme.muted} tickLine={false} axisLine={false} width={28} />
        <Tooltip
          cursor={{ fill: theme.grid }}
          contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8 }}
        />
        <Bar dataKey="count" name="Completed" fill={theme.accent} radius={[4, 4, 0, 0]} maxBarSize={16} />
      </BarChart>
    </ResponsiveContainer>
  )
}
