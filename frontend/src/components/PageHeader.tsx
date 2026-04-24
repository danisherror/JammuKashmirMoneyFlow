import { ReactNode } from 'react'

interface Props {
  title: string
  subtitle?: string
  right?: ReactNode
}

export default function PageHeader({ title, subtitle, right }: Props) {
  return (
    <div
      className="flex items-center justify-between px-6 py-4 border-b sticky top-0 z-10 backdrop-blur-sm"
      style={{ borderColor: '#1a2a3a', background: 'rgba(6,10,15,0.92)' }}
    >
      <div>
        <h1 className="display text-3xl tracking-widest text-gold">{title}</h1>
        {subtitle && <p className="mono text-[9px] text-dim tracking-widest mt-0.5">{subtitle}</p>}
      </div>
      {right && <div className="flex items-center gap-3">{right}</div>}
    </div>
  )
}
