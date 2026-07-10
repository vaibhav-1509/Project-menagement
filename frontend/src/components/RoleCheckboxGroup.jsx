export default function RoleCheckboxGroup({ roles, value, onChange }) {
  function toggle(roleId, checked) {
    const next = checked ? [...value, roleId] : value.filter((id) => id !== roleId)
    onChange(next)
  }

  return (
    <fieldset className="role-checkbox-group">
      <legend>Roles</legend>
      {roles.map((r) => (
        <label key={r.id} className="checkbox-row">
          <input
            type="checkbox"
            checked={value.includes(r.id)}
            onChange={(e) => toggle(r.id, e.target.checked)}
          />
          {r.name}
        </label>
      ))}
    </fieldset>
  )
}
