import { MapContainer, TileLayer, CircleMarker, Tooltip } from 'react-leaflet'
import { DISTRICT_COORDINATES } from '../lib/districtCoordinates'
import type { SchemeDistrictProgress } from '../lib/api'

interface MapWidgetProps {
  data: SchemeDistrictProgress[]
  height?: number
}

// Map center of J&K
const CENTER: [number, number] = [33.7, 74.8]

// Helper to get color based on utilization
function getColor(pct: number | null) {
  if (pct === null) return '#5a7a9a' // gray for missing
  if (pct >= 80) return '#00ff88' // green
  if (pct >= 50) return '#ffd700' // yellow
  return '#ff3366' // red
}

export default function MapWidget({ data, height = 400 }: MapWidgetProps) {
  // Find max allocated to scale bubbles
  const maxAllocated = Math.max(...data.map(d => d.funds_allocated_lakhs || 0), 1)

  return (
    <div className="panel overflow-hidden border-[#1a2a3a]" style={{ height, background: '#0a1018' }}>
      <MapContainer
        center={CENTER}
        zoom={7}
        zoomControl={true}
        scrollWheelZoom={false}
        style={{ height: '100%', width: '100%', background: '#0a1018' }}
      >
        <TileLayer
          url="https://mt1.google.com/vt/lyrs=m&gl=IN&x={x}&y={y}&z={z}"
          attribution='&copy; Google Maps'
          className="map-tiles-dark"
        />

        {data.map(dist => {
          const coords = DISTRICT_COORDINATES[dist.district_code]
          if (!coords) return null

          const allocated = dist.funds_allocated_lakhs || 0
          const utilized = dist.funds_utilized_lakhs || 0
          const utilPct = dist.utilization_pct
          
          // Calculate radius based on allocated funds relative to max
          // Minimum radius 8, max 35
          const baseRadius = allocated > 0 ? Math.sqrt(allocated / maxAllocated) * 35 : 5
          const radius = Math.max(8, baseRadius)
          
          const color = getColor(utilPct)

          return (
            <CircleMarker
              key={dist.district_code}
              center={coords}
              radius={radius}
              fillColor={color}
              fillOpacity={0.6}
              color={color}
              weight={1}
              eventHandlers={{
                mouseover: (e) => {
                  const layer = e.target;
                  layer.setStyle({ fillOpacity: 0.9, weight: 2 });
                },
                mouseout: (e) => {
                  const layer = e.target;
                  layer.setStyle({ fillOpacity: 0.6, weight: 1 });
                }
              }}
            >
              <Tooltip className="custom-tooltip" direction="top" offset={[0, -10]}>
                <div className="p-1 min-w-[150px]">
                  <div className="font-bold text-white border-b border-gray-700 pb-1 mb-1">{dist.district_name}</div>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                    <span className="text-gray-400">Allocated:</span>
                    <span className="text-white text-right">₹{allocated.toLocaleString('en-IN')}L</span>
                    <span className="text-gray-400">Utilized:</span>
                    <span className="text-white text-right">₹{utilized.toLocaleString('en-IN')}L</span>
                    <span className="text-gray-400">Utilization:</span>
                    <span className="text-right font-bold" style={{ color }}>{utilPct !== null ? `${utilPct}%` : 'N/A'}</span>
                  </div>
                </div>
              </Tooltip>
            </CircleMarker>
          )
        })}
      </MapContainer>
    </div>
  )
}
