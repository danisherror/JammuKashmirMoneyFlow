export default function ErrorBox({ message }: { message?: string }) {
  return (
    <div className="panel border-red-800/40 p-6 text-center">
      <div className="text-red mono text-xs mb-1">⚠ FETCH ERROR</div>
      <div className="text-dim mono text-[10px]">{message ?? 'Could not load data. API may be starting up.'}</div>
    </div>
  )
}
