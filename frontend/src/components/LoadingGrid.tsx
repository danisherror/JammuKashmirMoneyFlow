export default function LoadingGrid({ count = 6 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="panel h-28 animate-pulse" style={{ background: '#0d1520' }}>
          <div className="h-2 w-24 rounded mb-3" style={{ background: '#1a2a3a' }} />
          <div className="h-6 w-32 rounded mb-2" style={{ background: '#1a2a3a' }} />
          <div className="h-2 w-20 rounded" style={{ background: '#1a2a3a' }} />
        </div>
      ))}
    </div>
  )
}
