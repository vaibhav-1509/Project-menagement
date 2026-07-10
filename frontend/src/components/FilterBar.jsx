import SearchBox from './SearchBox'

export default function FilterBar({ filters, onChange, lookups, users, isAdmin }) {
  function set(key, value) {
    onChange({ ...filters, [key]: value === '' ? null : value })
  }

  function setPhase(value) {
    // Category/Sub-Category are scoped to a phase - clear both when the phase
    // changes so a stale selection from the old phase can't linger.
    onChange({ ...filters, phase_id: value === '' ? null : value, category_id: null, sub_category_id: null })
  }

  function setCategory(value) {
    onChange({ ...filters, category_id: value === '' ? null : value, sub_category_id: null })
  }

  function setProcessType(value) {
    // status_id's meaning flips between "overall mirror" and "this stage's
    // status" depending on whether a process type is selected - clear it so a
    // stale selection from the other mode can't silently misfilter.
    onChange({ ...filters, process_type_id: value === '' ? null : value, status_id: null })
  }

  const categories = lookups.categories.filter(
    (c) => !filters.phase_id || c.phaseId === Number(filters.phase_id)
  )
  const subCategories = lookups.subCategories.filter(
    (sc) => !filters.category_id || sc.categoryId === Number(filters.category_id)
  )

  return (
    <div className="filter-bar">
      <SearchBox value={filters.search ?? ''} onChange={(v) => set('search', v)} />

      <select value={filters.phase_id ?? ''} onChange={(e) => setPhase(e.target.value)}>
        <option value="">All Phases</option>
        {lookups.phases.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </select>

      <select value={filters.category_id ?? ''} onChange={(e) => setCategory(e.target.value)}>
        <option value="">All Categories</option>
        {categories.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </select>

      <select value={filters.sub_category_id ?? ''} onChange={(e) => set('sub_category_id', e.target.value)}>
        <option value="">All Sub-Categories</option>
        {subCategories.map((sc) => (
          <option key={sc.id} value={sc.id}>
            {sc.name}
          </option>
        ))}
      </select>

      <select value={filters.process_type_id ?? ''} onChange={(e) => setProcessType(e.target.value)}>
        <option value="">All Stages</option>
        {lookups.processTypes.map((pt) => (
          <option key={pt.id} value={pt.id}>
            {pt.name}
          </option>
        ))}
      </select>

      <select value={filters.status_id ?? ''} onChange={(e) => set('status_id', e.target.value)}>
        <option value="">All Statuses</option>
        {lookups.statuses.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
          </option>
        ))}
      </select>

      {isAdmin && (
        <select
          value={filters.assigned_to_user_id ?? ''}
          onChange={(e) => set('assigned_to_user_id', e.target.value)}
        >
          <option value="">Everyone</option>
          {users.map((u) => (
            <option key={u.UserID} value={u.UserID}>
              {u.Username}
            </option>
          ))}
        </select>
      )}
    </div>
  )
}
