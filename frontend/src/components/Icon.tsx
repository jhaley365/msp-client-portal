import { CSSProperties } from 'react'

export default function Icon({
  name,
  className = '',
  style,
}: {
  name: string
  className?: string
  style?: CSSProperties
}) {
  return (
    <span className={`material-symbols-rounded ${className}`} style={style}>
      {name}
    </span>
  )
}
