import React, { useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, CircleMarker, useMap } from 'react-leaflet';
import L from 'leaflet';
import ErrorBoundary from '../components/ErrorBoundary';

// Fix Leaflet icon URLs for standard markers in bundlers
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

// Custom Train Icon
const createTrainIcon = (trainType, delay) => {
  const isDelayed = typeof delay === 'number' && delay > 10;
  const bgColor = isDelayed ? '#DC2626' : trainType === 'VANDE_BHARAT' ? '#0284C7' : '#134074';
  return L.divIcon({
    className: 'custom-train-marker',
    html: `<div style="background-color: ${bgColor}; color: white; padding: 2px 5px; font-weight: bold; font-size: 9px; font-family: monospace; border: 1px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.4); text-align: center; white-space: nowrap; border-radius: 2px;">
      🚆 ${trainType ? String(trainType).substring(0, 4) : 'TRN'} ${isDelayed ? `(+${delay}m)` : ''}
    </div>`,
    iconSize: [64, 22],
    iconAnchor: [32, 11]
  });
};

// Strict coordinate validation
const isValidCoord = (lat, lon) => {
  if (lat === null || lat === undefined || lon === null || lon === undefined) return false;
  const nLat = Number(lat);
  const nLon = Number(lon);
  return !isNaN(nLat) && !isNaN(nLon) &&
         isFinite(nLat) && isFinite(nLon) &&
         nLat >= -90 && nLat <= 90 &&
         nLon >= -180 && nLon <= 180;
};

// Map view updater for bounds and centering
function MapViewUpdater({ center, zoom, bounds }) {
  const map = useMap();
  useEffect(() => {
    try {
      if (bounds && typeof bounds.isValid === 'function' && bounds.isValid()) {
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 12 });
      } else if (Array.isArray(center) && center.length === 2 && !isNaN(center[0]) && !isNaN(center[1])) {
        map.setView(center, zoom);
      }
    } catch (err) {
      console.warn('[ABPS MapViewUpdater] View update warning:', err);
    }
  }, [center, zoom, bounds, map]);
  return null;
}

function RailwayMapInner({
  stations = [],
  sections = [],
  movements = [],
  routePolyline = [],
  routeGeometry = null,
  corridorName = '',
  loading = false,
  routeError = null,
  noRouteFound = false,
  startStationDisplay = '',
  endStationDisplay = '',
  hasSelectedStations = false
}) {
  // Validate and sanitize stations
  const validStations = useMemo(() => {
    if (!Array.isArray(stations)) return [];
    return stations
      .filter((s) => s && isValidCoord(s.latitude, s.longitude))
      .map((s, idx) => ({
        ...s,
        code: s.code || s.station_code || 'STN',
        name: s.name || s.station_name || 'Station',
        latitude: Number(s.latitude),
        longitude: Number(s.longitude),
        sequence: s.sequence !== undefined ? s.sequence : idx + 1
      }));
  }, [stations]);

  // Validate and sanitize movements (trains)
  const validMovements = useMemo(() => {
    if (!Array.isArray(movements)) return [];
    return movements
      .filter((m) => m && isValidCoord(m.latitude, m.longitude))
      .map((m) => ({
        ...m,
        train_number: String(m.train_number || 'UNKNOWN'),
        train_name: m.train_name || 'Train',
        latitude: Number(m.latitude),
        longitude: Number(m.longitude)
      }));
  }, [movements]);

  // Build and validate authentic track coordinates from network geometry (NEVER straight line!)
  const trackCoordinates = useMemo(() => {
    const coords = [];

    // 1. If routePolyline prop is provided directly (e.g. real track vertices from RailwayNetworkService)
    if (Array.isArray(routePolyline) && routePolyline.length >= 2) {
      for (const pt of routePolyline) {
        if (Array.isArray(pt) && pt.length >= 2 && isValidCoord(pt[0], pt[1])) {
          coords.push([Number(pt[0]), Number(pt[1])]);
        }
      }
      if (coords.length >= 2) return coords;
    }

    // 2. If routeGeometry GeoJSON is provided: GeoJSON is [lon, lat], convert to [lat, lon]
    let geo = routeGeometry;
    if (typeof geo === 'string') {
      try { geo = JSON.parse(geo); } catch { geo = null; }
    }
    if (geo && geo.type === 'LineString' && Array.isArray(geo.coordinates)) {
      for (const pt of geo.coordinates) {
        if (Array.isArray(pt) && pt.length >= 2 && isValidCoord(pt[1], pt[0])) {
          coords.push([Number(pt[1]), Number(pt[0])]);
        }
      }
      if (coords.length >= 2) return coords;
    }

    // 3. Extract from section geometries
    if (Array.isArray(sections) && sections.length > 0) {
      for (const sec of sections) {
        if (!sec) continue;
        let secGeo = sec.geometry_geojson || sec.coordinates;
        if (typeof secGeo === 'string') {
          try { secGeo = JSON.parse(secGeo); } catch { secGeo = null; }
        }

        if (Array.isArray(secGeo)) {
          for (const pt of secGeo) {
            if (Array.isArray(pt) && pt.length >= 2 && isValidCoord(pt[0], pt[1])) {
              if (coords.length > 0) {
                const last = coords[coords.length - 1];
                if (Math.abs(last[0] - Number(pt[0])) < 1e-5 && Math.abs(last[1] - Number(pt[1])) < 1e-5) {
                  continue;
                }
              }
              coords.push([Number(pt[0]), Number(pt[1])]);
            }
          }
        } else if (secGeo && secGeo.type === 'LineString' && Array.isArray(secGeo.coordinates)) {
          for (const pt of secGeo.coordinates) {
            if (Array.isArray(pt) && pt.length >= 2 && isValidCoord(pt[1], pt[0])) {
              if (coords.length > 0) {
                const last = coords[coords.length - 1];
                if (Math.abs(last[0] - Number(pt[1])) < 1e-5 && Math.abs(last[1] - Number(pt[0])) < 1e-5) {
                  continue;
                }
              }
              coords.push([Number(pt[1]), Number(pt[0])]);
            }
          }
        }
      }
      if (coords.length >= 2) return coords;
    }

    // NEVER fallback to straight line between station coordinates!
    return [];
  }, [routePolyline, routeGeometry, sections]);

  const hasSelectedRoute = (Array.isArray(stations) && stations.length > 0) || Boolean(corridorName);

  // Compute map center and bounding box from track coordinates or stations
  const { center, zoom, bounds } = useMemo(() => {
    if (trackCoordinates.length >= 2) {
      try {
        const b = L.latLngBounds(trackCoordinates);
        const centerPt = b.getCenter();
        return { center: [centerPt.lat, centerPt.lng], zoom: 9, bounds: b };
      } catch (e) {
        // fallback to stations
      }
    }

    if (validStations.length > 0) {
      const avgLat = validStations.reduce((sum, s) => sum + s.latitude, 0) / validStations.length;
      const avgLon = validStations.reduce((sum, s) => sum + s.longitude, 0) / validStations.length;

      if (validStations.length >= 2) {
        try {
          const latLngs = validStations.map((s) => [s.latitude, s.longitude]);
          const b = L.latLngBounds(latLngs);
          return { center: [avgLat, avgLon], zoom: 8, bounds: b };
        } catch {
          return { center: [avgLat, avgLon], zoom: 8, bounds: null };
        }
      }
      return { center: [avgLat, avgLon], zoom: 11, bounds: null };
    }

    // Default to Southern Railway / Tamil Nadu hub
    return { center: [10.8505, 78.7047], zoom: 7, bounds: null };
  }, [trackCoordinates, validStations]);

  const getHeaderStatusText = () => {
    if (loading) return 'LOADING RAILWAY ROUTE...';
    if (noRouteFound) return 'NO ROUTE FOUND';
    if (routeError) return 'ROUTE NOTICE';
    if (!hasSelectedRoute && !hasSelectedStations) return 'NO ROUTE SELECTED';
    if (hasSelectedStations && validStations.length === 0) return 'ROUTE NOT LOADED';
    if (validMovements.length === 0) return 'LIVE TRAIN DATA: UNAVAILABLE';
    return `${validMovements.length} LIVE GPS TELEMETRY RAKES`;
  };

  return (
    <div className="cris-panel overflow-hidden border border-slate-300 shadow-sm">
      <div className="cris-panel-header flex items-center justify-between">
        <span>INTERACTIVE GIS RAILWAY NETWORK MAP {corridorName ? `(${corridorName.toUpperCase()})` : ''}</span>
        <span className="text-[10px] bg-slate-200 text-slate-800 px-2 py-0.5 border border-slate-400 font-mono font-bold">
          {getHeaderStatusText()}
        </span>
      </div>

      <div className="h-[440px] min-h-[420px] w-full relative bg-slate-100">
        {/* Top-right Status Overlays */}
        {loading && (
          <div className="absolute top-2 right-2 bg-blue-900/90 text-white border border-blue-700 px-2.5 py-1 text-[10px] font-mono z-[1000] shadow-md flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-blue-400 animate-ping"></span>
            LOADING RAILWAY ROUTE & GEOMETRY...
          </div>
        )}

        {!loading && !hasSelectedRoute && !hasSelectedStations && (
          <div className="absolute top-2 right-2 bg-slate-900/90 text-white border border-slate-700 px-2.5 py-1 text-[10px] font-mono z-[1000] shadow-md flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-slate-400"></span>
            NO ROUTE SELECTED
          </div>
        )}

        {!loading && hasSelectedStations && validStations.length === 0 && !routeError && !noRouteFound && (
          <div className="absolute top-2 right-2 bg-slate-800/90 text-white border border-slate-700 px-2.5 py-1 text-[10px] font-mono z-[1000] shadow-md flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-amber-400"></span>
            ROUTE NOT LOADED
          </div>
        )}

        {!loading && hasSelectedRoute && validStations.length > 0 && trackCoordinates.length < 2 && (
          <div className="absolute bottom-2 left-2 bg-slate-800/90 text-white border border-slate-700 px-2 py-1 text-[10px] font-mono z-[1000] shadow-sm">
            Route geometry is unavailable.
          </div>
        )}

        {!loading && hasSelectedRoute && validMovements.length === 0 && (
          <div className="absolute top-2 right-2 bg-slate-900/90 text-white border border-slate-700 px-2.5 py-1 text-[10px] font-mono z-[1000] shadow-md flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-amber-400"></span>
            LIVE TRAIN DATA: UNAVAILABLE
          </div>
        )}

        {/* Modal-style overlay for NO ROUTE FOUND */}
        {noRouteFound && (
          <div className="absolute inset-0 z-[1000] bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
            <div className="bg-white border-2 border-amber-400 p-5 rounded max-w-md w-full shadow-xl space-y-3">
              <div className="border-b border-amber-200 pb-2">
                <h4 className="font-mono font-black text-amber-900 text-xs tracking-wider uppercase">NO ROUTE FOUND</h4>
                <p className="text-xs text-slate-600 mt-1">No railway route could be generated between:</p>
              </div>
              <div className="space-y-1.5 font-bold text-xs text-slate-800 bg-amber-50/70 p-3 rounded border border-amber-200">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-emerald-600"></span>
                  <span>{startStationDisplay || 'Start Station'}</span>
                </div>
                <div className="text-slate-400 text-[10px] pl-4">and</div>
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-red-600"></span>
                  <span>{endStationDisplay || 'End Station'}</span>
                </div>
              </div>
              <p className="text-[11px] text-slate-500 italic">Please verify the selected stations.</p>
            </div>
          </div>
        )}

        {/* Modal-style overlay for other route loading errors */}
        {routeError && !noRouteFound && (
          <div className="absolute inset-0 z-[1000] bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
            <div className="bg-white border-2 border-red-400 p-5 rounded max-w-md w-full shadow-xl space-y-3">
              <div className="border-b border-red-200 pb-2">
                <h4 className="font-mono font-black text-red-900 text-xs tracking-wider uppercase">ROUTE LOADING NOTICE</h4>
                <p className="text-xs text-slate-700 mt-1 font-medium">{routeError}</p>
              </div>
              <p className="text-[11px] text-slate-500 italic">The rest of the application remains available.</p>
            </div>
          </div>
        )}

        <MapContainer
          center={center}
          zoom={zoom}
          scrollWheelZoom={true}
          style={{ height: '100%', width: '100%', minHeight: '420px' }}
        >
          <MapViewUpdater center={center} zoom={zoom} bounds={bounds} />

          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {/* Authentic Railway Track Polylines */}
          {trackCoordinates.length >= 2 && (
            <>
              {/* Dark Track Base */}
              <Polyline
                positions={trackCoordinates}
                color="#0B2545"
                weight={6}
                opacity={0.95}
              />
              {/* Railway Sleeper Track Dash */}
              <Polyline
                positions={trackCoordinates}
                color="#F8FAFC"
                weight={2}
                opacity={0.9}
                dashArray="6, 8"
              />
            </>
          )}

          {/* Valid Station Markers (Origin, Intermediate, Destination) */}
          {validStations.map((stn, idx) => {
            const isOrigin = idx === 0;
            const isDestination = idx === validStations.length - 1;
            const isIntermediate = !isOrigin && !isDestination;

            const markerColor = isOrigin ? '#064E3B' : isDestination ? '#7F1D1D' : '#0B2545';
            const fillColor = isOrigin ? '#10B981' : isDestination ? '#EF4444' : '#FFB703';
            const radius = isOrigin || isDestination ? 8 : 6;

            return (
              <CircleMarker
                key={stn.code ? `${stn.code}-${idx}` : `stn-${idx}`}
                center={[stn.latitude, stn.longitude]}
                radius={radius}
                pathOptions={{
                  color: markerColor,
                  fillColor: fillColor,
                  fillOpacity: 1,
                  weight: 2.5
                }}
              >
                <Popup>
                  <div className="text-[11px] font-sans">
                    <div className="font-bold text-[#0B2545] border-b pb-1 text-[12px] flex items-center justify-between gap-2">
                      <span>{stn.name} ({stn.code})</span>
                      <span className={`text-[9px] px-1.5 py-0.5 rounded font-mono font-bold text-white ${
                        isOrigin ? 'bg-emerald-700' : isDestination ? 'bg-red-700' : 'bg-blue-700'
                      }`}>
                        {isOrigin ? 'ORIGIN' : isDestination ? 'DESTINATION' : `HALT #${stn.sequence || idx + 1}`}
                      </span>
                    </div>
                    <div className="mt-1 text-slate-700">
                      Division: <strong>{stn.division || 'SR'}</strong>
                    </div>
                    {stn.distance_km !== undefined && (
                      <div className="text-slate-800 font-mono">
                        Distance from Origin: <strong>{stn.distance_km} km</strong>
                      </div>
                    )}
                    {stn.category && (
                      <div className="text-slate-600">
                        Category: <strong>{stn.category}</strong>
                      </div>
                    )}
                    <div className="text-slate-500 text-[10px] font-mono mt-0.5">
                      Lat/Lon: {stn.latitude.toFixed(4)}, {stn.longitude.toFixed(4)}
                    </div>
                  </div>
                </Popup>
              </CircleMarker>
            );
          })}

          {/* Live Train Moving Markers */}
          {validMovements.map((m) => (
            <Marker
              key={m.train_number}
              position={[m.latitude, m.longitude]}
              icon={createTrainIcon(m.train_type, m.delay_minutes)}
            >
              <Popup>
                <div className="text-[11px] font-sans min-w-[220px]">
                  <div className="font-bold text-blue-900 border-b pb-1 text-[12px] flex items-center justify-between gap-1">
                    <span>🚆 {m.train_number}</span>
                    <span className="text-[9px] px-1.5 py-0.5 rounded font-bold uppercase bg-emerald-100 text-emerald-800 border border-emerald-300">
                      {m.status || 'RUNNING'}
                    </span>
                  </div>
                  <div className="font-semibold text-slate-800 text-[11px] mt-1 mb-1">
                    {m.train_name}
                  </div>
                  <div className="grid grid-cols-2 gap-1 text-[10px] bg-slate-50 p-1.5 rounded border border-slate-200">
                    <div>Speed: <strong>{m.speed_kmh || 0} km/h</strong></div>
                    <div>
                      Delay:{' '}
                      <strong className={m.delay_minutes > 0 ? 'text-red-600' : 'text-emerald-700'}>
                        {m.delay_minutes > 0 ? `+${m.delay_minutes} min` : 'RIGHT TIME'}
                      </strong>
                    </div>
                    {m.current_station_code && (
                      <div>Station: <strong>{m.current_station_code}</strong></div>
                    )}
                    {m.next_halt && (
                      <div>Next: <strong>{m.next_halt}</strong></div>
                    )}
                    <div>Track: <strong>{m.direction || 'UP'} Line</strong></div>
                    <div>Source: <strong className="text-emerald-700">{m.source || 'LIVE RADAR'}</strong></div>
                  </div>
                  {m.last_updated && (
                    <div className="text-[9px] text-slate-500 font-mono mt-1 text-right">
                      Updated: {new Date(m.last_updated).toLocaleTimeString()}
                    </div>
                  )}
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
    </div>
  );
}

export default function RailwayMap(props) {
  return (
    <ErrorBoundary variant="map">
      <RailwayMapInner {...props} />
    </ErrorBoundary>
  );
}
