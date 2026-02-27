/**
 * Skeleton loader para tarjetas de evento mientras cargan
 */
export default function SkeletonCard() {
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden animate-pulse">
      {/* Imagen skeleton */}
      <div className="aspect-video bg-slate-700" />
      {/* Metadata skeleton */}
      <div className="p-3 space-y-2">
        <div className="h-3 bg-slate-700 rounded w-3/4" />
        <div className="h-3 bg-slate-700 rounded w-1/2" />
      </div>
    </div>
  )
}

/**
 * Skeleton para filas de tabla
 */
export function SkeletonFila() {
  return (
    <tr className="animate-pulse">
      <td className="px-4 py-3"><div className="w-14 h-10 bg-slate-700 rounded" /></td>
      <td className="px-4 py-3"><div className="h-4 bg-slate-700 rounded w-24" /></td>
      <td className="px-4 py-3"><div className="h-4 bg-slate-700 rounded w-12" /></td>
      <td className="px-4 py-3"><div className="h-4 bg-slate-700 rounded w-36" /></td>
      <td className="px-4 py-3"><div className="h-8 bg-slate-700 rounded w-20" /></td>
    </tr>
  )
}

/**
 * Skeleton para stats cards
 */
export function SkeletonStats() {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="bg-slate-800 border border-slate-700 rounded-xl p-5 animate-pulse">
          <div className="flex items-start justify-between">
            <div className="space-y-2">
              <div className="h-3 bg-slate-700 rounded w-24" />
              <div className="h-8 bg-slate-700 rounded w-16" />
            </div>
            <div className="w-10 h-10 bg-slate-700 rounded-lg" />
          </div>
          <div className="h-3 bg-slate-700 rounded w-32 mt-3" />
        </div>
      ))}
    </div>
  )
}
