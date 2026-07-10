import { useEffect, useState } from 'react'

export default function SearchBox({ value, onChange, placeholder = 'Search files...' }) {
  const [local, setLocal] = useState(value || '')

  useEffect(() => setLocal(value || ''), [value])

  useEffect(() => {
    const t = setTimeout(() => {
      if (local !== (value || '')) onChange(local)
    }, 300)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [local])

  return (
    <input
      type="search"
      className="search-box"
      value={local}
      onChange={(e) => setLocal(e.target.value)}
      placeholder={placeholder}
    />
  )
}
