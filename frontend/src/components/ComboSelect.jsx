import { useState } from 'react'

const NEW_VALUE = '__new__'

export default function ComboSelect({ value, onChange, options, placeholder, emptyLabel = 'Select...' }) {
  const matchesExisting = !value || options.some((o) => o.name === value)
  const [creating, setCreating] = useState(false)

  if (creating || !matchesExisting) {
    return (
      <div className="combo-select-create">
        <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} autoFocus />
        <button
          type="button"
          className="secondary"
          onClick={() => {
            setCreating(false)
            onChange('')
          }}
        >
          Choose existing
        </button>
      </div>
    )
  }

  return (
    <select
      value={value}
      onChange={(e) => {
        if (e.target.value === NEW_VALUE) {
          setCreating(true)
          onChange('')
        } else {
          onChange(e.target.value)
        }
      }}
    >
      <option value="">{emptyLabel}</option>
      {options.map((o) => (
        <option key={o.id} value={o.name}>
          {o.name}
        </option>
      ))}
      <option value={NEW_VALUE}>+ Add new...</option>
    </select>
  )
}
