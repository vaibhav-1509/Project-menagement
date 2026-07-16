function statusClass(status) {
  if (status === 'Complete') return 'status-pill active'
  if (status === 'Repair' || status === 'Failed') return 'status-pill warning'
  return 'status-pill'
}

export default function WorkedFilesTable({ rows }) {
  if (!rows || rows.length === 0) {
    return <p className="hint">No worked files in this range.</p>
  }

  return (
    <table className="users-table">
      <thead>
        <tr>
          <th>File</th>
          <th>Process</th>
          <th>Assigned To</th>
          <th>Status</th>
          <th>Completed</th>
          <th>Reassigned To</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={`${r.fileName}-${r.processType}-${r.assignedTs}-${i}`}>
            <td>{r.fileName}</td>
            <td>{r.processType}</td>
            <td>{r.assignedTo}</td>
            <td>
              <span className={statusClass(r.status)}>{r.status}</span>
            </td>
            <td>{r.completionTs ? new Date(r.completionTs).toLocaleString() : '-'}</td>
            <td>{r.reassignedTo || (r.status === 'Repair' ? 'Not yet reassigned' : '-')}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
