import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Radio, MapPin, Gauge, Clock, ArrowRight, ShieldCheck, RefreshCw, AlertCircle, Layers, Search } from 'lucide-react';
import { getLiveTrainMovements, getLiveCorridorData, getStations, getSections, getCorridors, getCorridorGeometry, getTimeDistanceData, validateRoute, getDataStatus } from '../services/api';
import RailwayMap from '../maps/RailwayMap';
import StationAutocomplete from '../components/StationAutocomplete';

export default function TrainPosition() {
  const [corridors, setCorridors] = useState([]);
  const [corridorSearch, setCorridorSearch] = useState('');
  const [selectedCorridorId, setSelectedCorridorId] = useState(null);
  const [selectedCorridorName, setSelectedCorridorName] = useState('');
  const [startCode, setStartCode] = useState('');
  const [endCode, setEndCode] = useState('');
  const [routeMsg, setRouteMsg] = useState('');
  const [routeError, setRouteError] = useState(null);
  const [noRouteFound, setNoRouteFound] = useState(false);
  const [startStationDisplay, setStartStationDisplay] = useState('');
  const [endStationDisplay, setEndStationDisplay] = useState('');

  const [movements, setMovements] = useState([]);
  const [corridorSummary, setCorridorSummary] = useState({
    scheduledCount: 0,
    liveCount: 0,
    unavailableCount: 0,
    status: 'UNAVAILABLE',
    reason: ''
  });
  const [stations, setStations] = useState([]);
  const [sections, setSections] = useState([]);
  const [routeData, setRouteData] = useState(null);
  const [routePolyline, setRoutePolyline] = useState([]);
  const [loading, setLoading] = useState(false);
  const [routeLoading, setRouteLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshMessage, setRefreshMessage] = useState('');
  const [dataStatus, setDataStatus] = useState({
    status: 'UNAVAILABLE',
    provider: 'Checking Provider Status...',
    is_live: false,
    clock_display: ''
  });

  const requestIdRef = useRef(0);

  const filteredCorridors = useMemo(() => {
    const valid = corridors.filter(c => c.prototype_code && /^C(0[1-9]|[1-3][0-9]|4[0-6])$/.test(c.prototype_code));
    if (!corridorSearch.trim()) return valid;
    const q = corridorSearch.trim().toLowerCase();
    return valid.filter(c =>
      (c.name && c.name.toLowerCase().includes(q)) ||
      (c.prototype_code && c.prototype_code.toLowerCase().includes(q)) ||
      (c.start_station_code && c.start_station_code.toLowerCase().includes(q)) ||
      (c.end_station_code && c.end_station_code.toLowerCase().includes(q))
    );
  }, [corridors, corridorSearch]);

  // Poll movements & candidate discovery every 5 seconds
  useEffect(() => {
    const pollMovements = async () => {
      try {
        if (selectedCorridorId) {
          const res = await getLiveCorridorData(selectedCorridorId, false);
          if (res?.data && Array.isArray(res.data.trains)) {
            setMovements(res.data.trains);
            setCorridorSummary({
              scheduledCount: res.data.scheduledTrainCount || res.data.trains.length,
              liveCount: res.data.liveAvailableCount || 0,
              unavailableCount: res.data.liveUnavailableCount || 0,
              status: res.data.liveStatus || 'UNAVAILABLE',
              reason: res.data.reason || ''
            });
          }
        } else {
          const res = await getLiveTrainMovements(null, false);
          if (Array.isArray(res?.data) && res.data.length > 0) {
            setMovements(res.data);
          }
        }
      } catch (err) {
        console.warn('[ABPS] Movement polling notice:', err);
      }
    };

    const interval = setInterval(pollMovements, 5000);
    return () => clearInterval(interval);
  }, [selectedCorridorId]);

  useEffect(() => {
    const loadMasterCorridors = async () => {
      try {
        const res = await getCorridors();
        setCorridors(res.data || []);
      } catch (err) {
        console.error('[ABPS] Failed to load corridors:', err);
      }
    };
    const fetchStatus = async () => {
      try {
        const res = await getDataStatus();
        if (res?.data) setDataStatus(res.data);
      } catch (err) {
        console.warn('Failed to fetch data status:', err);
      }
    };
    loadMasterCorridors();
    fetchStatus();
    const interval = setInterval(fetchStatus, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleRefreshRadarFeed = async () => {
    setRefreshing(true);
    setRefreshMessage('Refreshing TN live trains...');
    try {
      if (selectedCorridorId) {
        const res = await getLiveCorridorData(selectedCorridorId, true);
        if (res?.data && Array.isArray(res.data.trains)) {
          setMovements(res.data.trains);
          setCorridorSummary({
            scheduledCount: res.data.scheduledTrainCount || res.data.trains.length,
            liveCount: res.data.liveAvailableCount || 0,
            unavailableCount: res.data.liveUnavailableCount || 0,
            status: res.data.liveStatus || 'UNAVAILABLE',
            reason: res.data.reason || ''
          });
          if (res.data.liveAvailableCount > 0) {
            setRefreshMessage(`Updated ${res.data.liveAvailableCount} live trains (${res.data.liveUnavailableCount} scheduled without live data)`);
          } else {
            setRefreshMessage(`Live telemetry unavailable (${res.data.reason || 'Remote'}); showing ${res.data.trains.length} scheduled candidates`);
          }
        }
      } else {
        const res = await getLiveTrainMovements(null, true);
        const updated = Array.isArray(res?.data) ? res.data : [];
        setMovements(updated);
        setRefreshMessage(updated.length > 0 ? `Updated ${updated.length} live trains` : 'No fresh telemetry available (cooldown active)');
      }

      const stRes = await getDataStatus();
      if (stRes?.data) setDataStatus(stRes.data);
    } catch (err) {
      console.error('[ABPS] Refresh radar error:', err);
      setRefreshMessage('Live provider rate limited; showing latest available telemetry');
    } finally {
      setRefreshing(false);
      setTimeout(() => setRefreshMessage(''), 6000);
    }
  };

  const loadCorridorTelemetry = async (corrId, parentReqId = null, keepRoute = false) => {
    if (!corrId) {
      if (!keepRoute) {
        setStations([]);
        setSections([]);
        setSelectedCorridorName('');
      }
      setMovements([]);
      setCorridorSummary({
        scheduledCount: 0,
        liveCount: 0,
        unavailableCount: 0,
        status: 'UNAVAILABLE',
        reason: ''
      });
      return;
    }

    const reqId = parentReqId || ++requestIdRef.current;
    if (!keepRoute) {
      setRouteLoading(true);
    }
    setLoading(true);

    // Step 1: Immediately load authentic corridor geometry and station nodes (<20ms)
    getCorridorGeometry(corrId).then((geomRes) => {
      if (reqId !== requestIdRef.current) return;
      if (geomRes && geomRes.data) {
        const gData = geomRes.data;
        if (Array.isArray(gData.leaflet_latlngs) && gData.leaflet_latlngs.length > 0) {
          setRoutePolyline(gData.leaflet_latlngs);
        }
        const stnNodes = Array.isArray(gData.station_nodes) ? gData.station_nodes : [];
        if (!keepRoute && stnNodes.length > 0) {
          setStations(stnNodes);
        }
        if (!keepRoute && Array.isArray(gData.section_nodes) && gData.section_nodes.length > 0) {
          setSections(gData.section_nodes);
        }
        const startC = gData.properties?.start_station_code || stnNodes[0]?.station_code || stnNodes[0]?.code || (Array.isArray(gData.stations) ? gData.stations[0] : '');
        const endC = gData.properties?.end_station_code || stnNodes[stnNodes.length - 1]?.station_code || stnNodes[stnNodes.length - 1]?.code || (Array.isArray(gData.stations) ? gData.stations[gData.stations.length - 1] : '');
        const startN = stnNodes[0]?.station_name || stnNodes[0]?.name || startC;
        const endN = stnNodes[stnNodes.length - 1]?.station_name || stnNodes[stnNodes.length - 1]?.name || endC;

        if (gData.properties?.name) {
          setSelectedCorridorName(gData.properties.name);
        }

        setRouteData({
          valid: true,
          status: 'AUTHENTIC RAILWAY ROUTE',
          corridor_id: gData.properties?.corridor_id,
          prototype_code: gData.properties?.prototype_code,
          name: gData.properties?.name || '',
          start_station_code: startC,
          end_station_code: endC,
          start_station_name: startN,
          end_station_name: endN,
          from: { division: gData.properties?.division || 'SR' },
          to: { division: gData.properties?.division || 'SR' },
          distance_km: gData.properties?.total_distance_km || 0,
          sections_count: gData.properties?.sections_count || (gData.sections?.length || 0),
          intermediate_stations_count: Math.max(0, (stnNodes.length > 0 ? stnNodes.length : (gData.stations?.length || 0)) - 2),
          geometry: gData.geometry
        });

        setStartStationDisplay(startC ? `${startC} — ${startN}` : '');
        setEndStationDisplay(endC ? `${endC} — ${endN}` : '');
        setRouteLoading(false);
      }
    }).catch((err) => {
      console.warn('[ABPS] Geometry load error:', err);
    });

    // Step 2: Query candidate trains and live status directly from Live Corridor service
    try {
      const liveRes = await getLiveCorridorData(corrId, false);
      if (reqId !== requestIdRef.current) return;
      if (liveRes?.data && Array.isArray(liveRes.data.trains)) {
        setMovements(liveRes.data.trains);
        setCorridorSummary({
          scheduledCount: liveRes.data.scheduledTrainCount || liveRes.data.trains.length,
          liveCount: liveRes.data.liveAvailableCount || 0,
          unavailableCount: liveRes.data.liveUnavailableCount || 0,
          status: liveRes.data.liveStatus || 'UNAVAILABLE',
          reason: liveRes.data.reason || ''
        });
      }
    } catch (err) {
      console.warn('[ABPS] Live corridor telemetry fetch notice:', err);
    }

    // Step 3: Concurrently fetch time-distance data for sections and timeline
    try {
      const tdRes = await getTimeDistanceData(corrId);
      if (reqId !== requestIdRef.current) return;

      if (tdRes && tdRes.data) {
        const data = tdRes.data;
        if (!keepRoute && Array.isArray(data.stations) && data.stations.length > 0) {
          const validStns = data.stations.filter(
            s => s && s.latitude !== undefined && s.longitude !== undefined &&
              !isNaN(Number(s.latitude)) && !isNaN(Number(s.longitude))
          ).map((s, idx) => ({
            ...s,
            code: s.station_code || s.code || `STN_${idx}`,
            name: s.station_name || s.name || s.station_code || s.code || `Station ${idx + 1}`
          }));
          if (validStns.length > 0) {
            setStations(validStns);
          }
        }

        if (!keepRoute && Array.isArray(data.sections) && data.sections.length > 0) {
          setSections(data.sections);
        }

        if (data.corridor?.name) {
          setSelectedCorridorName(data.corridor.name);
        }

        if (data.provenance) {
          setDataStatus(prev => ({
            ...prev,
            status: data.provenance.source || prev.status,
            provider: data.provenance.provider || prev.provider,
            is_live: data.provenance.is_live,
            clock_display: data.provenance.clock_display
          }));
        }
      }
    } catch (err) {
      if (reqId !== requestIdRef.current) return;
      console.warn('[ABPS] Train telemetry fetch warning (map remains intact):', err);
    } finally {
      if (reqId === requestIdRef.current) {
        setLoading(false);
        setRouteLoading(false);
      }
    }
  };

  const handleCorridorChange = (corrId) => {
    const parsedId = corrId ? parseInt(corrId) : null;
    setSelectedCorridorId(parsedId);
    setStartCode('');
    setEndCode('');
    setRouteMsg('');
    setRouteError(null);
    setNoRouteFound(false);
    loadCorridorTelemetry(parsedId);
  };

  const selectPresetCorridor = (protoCode) => {
    const found = corridors.find(c => c.prototype_code === protoCode);
    if (found) {
      handleCorridorChange(found.id);
    }
  };

  const handleCustomRouteSearch = async (e, overrideStart, overrideEnd) => {
    if (e && e.preventDefault) e.preventDefault();
    const reqId = ++requestIdRef.current;

    const s = (overrideStart !== undefined ? overrideStart : startCode).trim().toUpperCase();
    const ed = (overrideEnd !== undefined ? overrideEnd : endCode).trim().toUpperCase();

    setStartStationDisplay(s);
    setEndStationDisplay(ed);

    // Step 1: Validate presence
    if (!s || !ed) {
      setRouteMsg('Please specify both Start and End station codes.');
      setRouteError('Please specify both Start and End station codes.');
      setNoRouteFound(false);
      return;
    }

    // Step 2: Reject same station
    if (s === ed) {
      setRouteMsg(`Start and end stations must be different (${s}).`);
      setRouteError(`Start and destination stations cannot be the same (${s}). Please select distinct stations.`);
      setNoRouteFound(false);
      return;
    }

    // Step 3: Validate station code format
    const codeRegex = /^[A-Z0-9]{2,10}$/;
    if (!codeRegex.test(s) || !codeRegex.test(ed)) {
      const invalidCode = !codeRegex.test(s) ? s : ed;
      setRouteMsg(`Invalid station code format: "${invalidCode}".`);
      setRouteError(`Invalid station code format: "${invalidCode}". Station codes must be 2 to 10 alphanumeric characters (e.g. MAS, TPJ, CVP, TEN).`);
      setNoRouteFound(false);
      return;
    }

    setRouteLoading(true);
    setLoading(true);
    setRouteError(null);
    setNoRouteFound(false);
    setRouteMsg(`Resolving railway route: ${s} → ${ed}...`);

    try {
      const res = await validateRoute(s, ed);
      if (reqId !== requestIdRef.current) return;

      // Validate response structure
      if (!res || !res.data) {
        throw new Error('Received an empty response from the railway routing service.');
      }

      const data = res.data;

      if (!data.valid) {
        const errorMsg = data.message || `Unable to load railway route between ${s} and ${ed}.`;
        setRouteMsg(errorMsg);
        setRouteError(errorMsg);
        setNoRouteFound(true);
        setStations([]);
        setSections([]);
        setMovements([]);
        setRouteData(null);
        setRoutePolyline([]);
        setSelectedCorridorName('');
        return;
      }

      // Validate stations array and coordinates
      const rawStations = Array.isArray(data.stations) ? data.stations : [];
      const validStns = rawStations.filter(
        stn => stn && typeof stn === 'object' &&
          stn.latitude !== undefined && stn.latitude !== null &&
          stn.longitude !== undefined && stn.longitude !== null &&
          !isNaN(Number(stn.latitude)) && !isNaN(Number(stn.longitude)) &&
          Number(stn.latitude) >= -90 && Number(stn.latitude) <= 90 &&
          Number(stn.longitude) >= -180 && Number(stn.longitude) <= 180
      );

      const rawSections = Array.isArray(data.sections) ? data.sections : [];

      const startName = data.start_station_name || s;
      const endName = data.end_station_name || ed;
      setStartStationDisplay(`${s} — ${startName}`);
      setEndStationDisplay(`${ed} — ${endName}`);

      setStations(validStns);
      setSections(rawSections);
      setRouteData(data);
      setRoutePolyline(Array.isArray(data.polyline) ? data.polyline : []);
      setSelectedCorridorName(data.corridor_name || `${startName} ↔ ${endName}`);

      setRouteMsg(`Route Established: ${startName} (${s}) to ${endName} (${ed}) — ${data.distance_km || 0} km`);
      setRouteError(null);
      setNoRouteFound(false);

      // Refresh master corridor list in background
      getCorridors().then((cRes) => {
        if (reqId === requestIdRef.current && Array.isArray(cRes.data)) {
          setCorridors(cRes.data);
        }
      }).catch(() => { });

      if (data.corridor_id) {
        setSelectedCorridorId(data.corridor_id);
        loadCorridorTelemetry(data.corridor_id, reqId, true /* keepRoute */);
      } else {
        setMovements([]);
      }

    } catch (err) {
      if (reqId !== requestIdRef.current) return;
      console.error('[ABPS] Route validation error:', err);

      let userMsg = `Unable to load railway route between ${s} and ${ed}.`;
      let is404 = false;

      if (err.response) {
        const status = err.response.status;
        const respMsg = err.response.data?.message || err.response.data?.detail;
        if (status === 404) {
          userMsg = respMsg || `No railway corridor or route found connecting ${s} and ${ed}.`;
          is404 = true;
        } else if (status === 400) {
          userMsg = respMsg || `Invalid route parameters requested for ${s} → ${ed}.`;
        } else if (status === 422) {
          userMsg = `Station code validation failed on the server for ${s} → ${ed}.`;
        } else if (status >= 500) {
          userMsg = `The railway planning engine encountered a temporary server error (HTTP ${status}) while calculating route ${s} → ${ed}.`;
        }
      } else if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
        userMsg = `Railway route calculation timed out while querying ${s} → ${ed}. Please try again.`;
      } else if (err.message) {
        userMsg = err.message;
      }

      setRouteMsg(userMsg);
      setRouteError(userMsg);
      setNoRouteFound(is404);
      setStations([]);
      setSections([]);
      setMovements([]);
      setRouteData(null);
      setRoutePolyline([]);
    } finally {
      if (reqId === requestIdRef.current) {
        setRouteLoading(false);
        setLoading(false);
      }
    }
  };

  const selectPresetRoute = (from, to) => {
    setStartCode(from);
    setEndCode(to);
    handleCustomRouteSearch(null, from, to);
  };

  return (
    <div className="p-3 space-y-3">
      {/* Top Header */}
      <div className="bg-white p-3 border border-slate-300 flex flex-wrap items-center justify-between gap-2 shadow-sm">
        <div>
          <h2 className="font-bold text-sm text-[#0B2545] uppercase tracking-wide flex items-center gap-1.5">
            <Radio className="w-4 h-4 text-emerald-600 animate-pulse" />
            LIVE TRAIN POSITION & GEOMETRIC SECTION MAPPING (RAILRADAR INTEGRATED)
          </h2>
          <p className="text-[11px] text-slate-500">
            Real-time GPS telemetry from RailRadar projected onto selected railway corridor geometry.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {selectedCorridorId && (
            <>
              <span className="bg-blue-950 text-blue-200 border border-blue-500 px-2.5 py-1 text-xs font-mono font-bold flex items-center gap-1.5 shadow-sm rounded">
                <Layers className="w-3.5 h-3.5 text-blue-400" />
                TODAY'S SCHEDULED TRAINS: {corridorSummary.scheduledCount || movements.length}
              </span>
              <span className="bg-emerald-950 text-emerald-300 border border-emerald-500 px-2.5 py-1 text-xs font-mono font-bold flex items-center gap-1.5 shadow-sm rounded">
                <Radio className="w-3.5 h-3.5 text-emerald-400" />
                LIVE AVAILABLE: {corridorSummary.liveCount}
              </span>
              <span className="bg-amber-950 text-amber-300 border border-amber-500 px-2.5 py-1 text-xs font-mono font-bold flex items-center gap-1.5 shadow-sm rounded">
                <Clock className="w-3.5 h-3.5 text-amber-400" />
                LIVE UNAVAILABLE: {corridorSummary.unavailableCount || Math.max(0, (corridorSummary.scheduledCount || movements.length) - corridorSummary.liveCount)}
              </span>
            </>
          )}

          {dataStatus.status === 'LIVE RADAR' || dataStatus.status === 'LIVE' ? (
            <span className="bg-emerald-900 text-emerald-300 border border-emerald-500 px-2.5 py-1 text-xs font-mono font-bold flex items-center gap-1.5 shadow-sm rounded">
              <Radio className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
              LIVE TRAIN DATA: LIVE
            </span>
          ) : dataStatus.status === 'STALE' ? (
            <span className="bg-amber-900 text-amber-200 border border-amber-500 px-2.5 py-1 text-xs font-mono font-bold flex items-center gap-1.5 shadow-sm rounded">
              <Clock className="w-3.5 h-3.5 text-amber-300" />
              LIVE TRAIN DATA: STALE
            </span>
          ) : dataStatus.status === 'CACHED' ? (
            <span className="bg-amber-900 text-amber-300 border border-amber-500 px-2.5 py-1 text-xs font-mono font-bold flex items-center gap-1.5 shadow-sm rounded">
              <Clock className="w-3.5 h-3.5 text-amber-400" />
              LIVE TRAIN DATA: CACHED
            </span>
          ) : dataStatus.status === 'ERROR' ? (
            <span className="bg-red-900 text-red-200 border border-red-500 px-2.5 py-1 text-xs font-mono font-bold flex items-center gap-1.5 shadow-sm rounded">
              <AlertCircle className="w-3.5 h-3.5 text-red-400" />
              {dataStatus.provider?.includes('CONFIGURATION') ? 'RAILRADAR CONFIGURATION ERROR' : 'LIVE TRAIN DATA: ERROR'}
            </span>
          ) : (
            <span className="bg-slate-800 text-slate-300 border border-slate-600 px-2.5 py-1 text-xs font-mono font-bold flex items-center gap-1.5 shadow-sm rounded">
              <Radio className="w-3.5 h-3.5 text-slate-400" />
              LIVE TRAIN DATA: UNAVAILABLE
            </span>
          )}

          <button
            onClick={handleRefreshRadarFeed}
            disabled={refreshing}
            className="cris-btn cris-btn-secondary text-[11px] flex items-center gap-1 shadow-sm"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            {refreshing ? 'Refreshing TN live trains...' : 'Refresh Radar Feed'}
          </button>
        </div>
      </div>

      {refreshMessage && (
        <div className={`text-xs px-3 py-1.5 rounded font-mono font-semibold border flex items-center justify-between ${refreshMessage.includes('rate limited') || refreshMessage.includes('error')
            ? 'bg-amber-50 border-amber-300 text-amber-900'
            : refreshMessage.includes('Updated')
              ? 'bg-emerald-50 border-emerald-300 text-emerald-900'
              : 'bg-blue-50 border-blue-300 text-blue-900'
          }`}>
          <span>📡 {refreshMessage}</span>
          <button onClick={() => setRefreshMessage('')} className="text-slate-400 hover:text-slate-600 font-bold ml-2">✕</button>
        </div>
      )}

      {/* Dynamic Corridor & Route Selection Bar */}
      <div className="bg-slate-100 p-2.5 border border-slate-300 space-y-2 text-xs">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center space-x-1.5">
              <span className="font-bold text-slate-700 uppercase text-[11px]">Corridor:</span>
              <div className="relative flex items-center">
                <Search className="w-3 h-3 text-slate-400 absolute left-2 pointer-events-none" />
                <input
                  type="text"
                  placeholder="Filter (e.g. Salem, MDU, C40)..."
                  value={corridorSearch}
                  onChange={(e) => setCorridorSearch(e.target.value)}
                  className="font-mono text-[11px] bg-white border border-slate-300 pl-6 pr-2 py-1 w-44 rounded focus:outline-none focus:border-[#0B2545]"
                />
              </div>
              <select
                value={selectedCorridorId || ''}
                onChange={(e) => handleCorridorChange(e.target.value)}
                className="font-bold text-slate-900 bg-white border border-slate-300 px-2.5 py-1 text-xs cursor-pointer rounded max-w-xs md:max-w-md truncate"
              >
                <option value="">[ -- SELECT OPERATIONAL CORRIDOR (C01–C46) -- ]</option>
                {filteredCorridors.map((c) => (
                  <option key={c.id} value={c.id}>
                    [{c.prototype_code}] {c.name}
                  </option>
                ))}
              </select>
            </div>

            <span className="text-slate-400 font-bold hidden md:inline">|</span>

            {/* Dynamic Station Route Selection with StationAutocomplete */}
            <form onSubmit={handleCustomRouteSearch} className="flex flex-wrap items-center gap-2">
              <span className="text-slate-600 font-bold text-[11px]">Dynamic Route:</span>
              <div className="w-48">
                <StationAutocomplete
                  id="tp_start_station"
                  placeholder="From (e.g. CVP)"
                  value={startCode}
                  onChange={(code) => setStartCode(code)}
                />
              </div>
              <span className="text-slate-400 font-bold">→</span>
              <div className="w-48">
                <StationAutocomplete
                  id="tp_end_station"
                  placeholder="To (e.g. TEN)"
                  value={endCode}
                  onChange={(code) => setEndCode(code)}
                />
              </div>
              <button
                type="submit"
                className="cris-btn cris-btn-primary text-xs py-1 px-3 shadow-sm"
              >
                Load Route & Map
              </button>
            </form>
          </div>

          {routeMsg && (
            <div className="text-[11px] font-mono text-blue-900 font-semibold bg-blue-50 border border-blue-200 px-2.5 py-1 rounded shadow-xs">
              {routeMsg}
            </div>
          )}
        </div>

        {/* Quick Authoritative Corridor Presets */}
        <div className="flex flex-wrap items-center gap-1.5 pt-1 border-t border-slate-200 text-[10px]">
          <span className="text-slate-500 font-semibold uppercase">Authoritative TN Corridors:</span>
          <button
            type="button"
            onClick={() => selectPresetCorridor('C40')}
            className="px-2 py-0.5 bg-blue-50 hover:bg-blue-100 text-blue-900 border border-blue-300 rounded font-semibold transition-colors"
          >
            ⭐ C40: Madurai → Tirunelveli (MDU–TEN)
          </button>
          <button
            type="button"
            onClick={() => selectPresetCorridor('C15')}
            className="px-2 py-0.5 bg-white hover:bg-slate-100 text-slate-700 border border-slate-300 rounded font-semibold transition-colors"
          >
            C15: Salem → Jolarpettai (SA–JTJ)
          </button>
          <button
            type="button"
            onClick={() => selectPresetCorridor('C31')}
            className="px-2 py-0.5 bg-white hover:bg-slate-100 text-slate-700 border border-slate-300 rounded font-semibold transition-colors"
          >
            C31: Thanjavur → Karaikal (TJ–KIK)
          </button>
          <button
            type="button"
            onClick={() => selectPresetCorridor('C37')}
            className="px-2 py-0.5 bg-white hover:bg-slate-100 text-slate-700 border border-slate-300 rounded font-semibold transition-colors"
          >
            C37: Trichy → Manamadurai (TPJ–MNM)
          </button>
          <button
            type="button"
            onClick={() => selectPresetCorridor('C45')}
            className="px-2 py-0.5 bg-white hover:bg-slate-100 text-slate-700 border border-slate-300 rounded font-semibold transition-colors"
          >
            C45: Madurai → Bodinayakkanur (MDU–BDNK)
          </button>
          <button
            type="button"
            onClick={() => selectPresetCorridor('C23')}
            className="px-2 py-0.5 bg-white hover:bg-slate-100 text-slate-700 border border-slate-300 rounded font-semibold transition-colors"
          >
            C23: Nilgiri Mountain Railway (MTP–UAM)
          </button>
          <button
            type="button"
            onClick={() => selectPresetCorridor('C21')}
            className="px-2 py-0.5 bg-white hover:bg-slate-100 text-slate-700 border border-slate-300 rounded font-semibold transition-colors"
          >
            C21: Erode → Coimbatore (ED–CBE)
          </button>
          <button
            type="button"
            onClick={() => selectPresetCorridor('C01')}
            className="px-2 py-0.5 bg-white hover:bg-slate-100 text-slate-700 border border-slate-300 rounded font-semibold transition-colors"
          >
            C01: Chennai → Arakkonam (MAS–AJJ)
          </button>
        </div>
      </div>

      {/* Section 5 Corridor Selection Summary Box */}
      {selectedCorridorId && corridors.find(c => c.id === selectedCorridorId) && (() => {
        const corr = corridors.find(c => c.id === selectedCorridorId);
        return (
          <div className="bg-white border-2 border-[#0B2545] p-2.5 shadow-xs flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] font-bold text-[#FFB703] bg-[#0B2545] px-1.5 py-0.5">
                {corr.prototype_code || 'CORRIDOR'}
              </span>
              <strong className="text-slate-900 font-bold text-sm">
                {corr.name}
              </strong>
            </div>
            <div className="flex items-center gap-4 text-slate-700 font-mono text-[11px]">
              <div><span className="text-slate-400">Start:</span> <strong className="text-slate-900">{corr.start_station_code}</strong></div>
              <div><span className="text-slate-400">End:</span> <strong className="text-slate-900">{corr.end_station_code}</strong></div>
              <div><span className="text-slate-400">Sections:</span> <strong className="text-slate-900">{sections.length || corr.sections_count || 3}</strong></div>
              <div><span className="text-slate-400">Stations:</span> <strong className="text-slate-900">{stations.length || corr.stations_count || 8}</strong></div>
            </div>
          </div>
        );
      })()}

      {/* Route Error / Notice Banner if present */}
      {routeError && (
        <div className="bg-red-50 border-l-4 border-red-500 p-2.5 text-xs text-red-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
            <span>{routeError}</span>
          </div>
          <button
            type="button"
            onClick={() => setRouteError(null)}
            className="text-red-500 hover:text-red-700 font-bold ml-2 text-xs"
          >
            ✕
          </button>
        </div>
      )}

      {/* Route Metadata Summary Panel (Section 15) */}
      {routeData && routeData.valid && (
        <div className="bg-white border-2 border-[#0B2545] p-3 shadow-sm rounded-sm space-y-2.5">
          <div className="flex items-center justify-between border-b border-slate-200 pb-2">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
              <h3 className="font-bold text-xs uppercase tracking-wider text-[#0B2545]">
                OPERATIONAL RAILWAY ROUTE SUMMARY — TOPOLOGICAL NETWORK ALIGNMENT
              </h3>
            </div>
            <div className="flex items-center gap-2">
              <span className="bg-emerald-100 text-emerald-800 text-[10px] font-bold px-2 py-0.5 rounded border border-emerald-300 font-mono">
                ROUTE STATUS: {routeData.status || 'VALID'}
              </span>
              <span className="bg-blue-50 text-blue-800 text-[10px] font-mono px-2 py-0.5 rounded border border-blue-200">
                {routePolyline.length} TRACK GEOMETRY VERTICES
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-6 gap-2 text-xs">
            {/* FROM */}
            <div className="bg-slate-50 p-2 border border-slate-200 rounded">
              <div className="text-[10px] text-slate-500 font-bold uppercase">FROM</div>
              <div className="font-bold text-[#0B2545] text-sm mt-0.5">{routeData.start_station_code}</div>
              <div className="text-[11px] text-slate-600 truncate">{routeData.start_station_name}</div>
              <div className="text-[9px] text-slate-400 mt-0.5">Div: {routeData.from?.division || 'SR'}</div>
            </div>

            {/* TO */}
            <div className="bg-slate-50 p-2 border border-slate-200 rounded">
              <div className="text-[10px] text-slate-500 font-bold uppercase">TO</div>
              <div className="font-bold text-[#0B2545] text-sm mt-0.5">{routeData.end_station_code}</div>
              <div className="text-[11px] text-slate-600 truncate">{routeData.end_station_name}</div>
              <div className="text-[9px] text-slate-400 mt-0.5">Div: {routeData.to?.division || 'SR'}</div>
            </div>

            {/* ROUTE DISTANCE */}
            <div className="bg-slate-50 p-2 border border-slate-200 rounded">
              <div className="text-[10px] text-slate-500 font-bold uppercase">ROUTE DISTANCE</div>
              <div className="font-bold text-emerald-700 text-sm mt-0.5 font-mono">
                {routeData.distance_km || 0} km
              </div>
              <div className="text-[9px] text-emerald-600 font-semibold mt-0.5">AUTHENTIC TRACK DISTANCE</div>
            </div>

            {/* SECTIONS */}
            <div className="bg-slate-50 p-2 border border-slate-200 rounded">
              <div className="text-[10px] text-slate-500 font-bold uppercase">SECTIONS</div>
              <div className="font-bold text-slate-800 text-sm mt-0.5 font-mono">
                {routeData.sections_count || sections.length}
              </div>
              <div className="text-[9px] text-slate-500 mt-0.5">Block Sections</div>
            </div>

            {/* INTERMEDIATE STATIONS COUNT */}
            <div className="bg-slate-50 p-2 border border-slate-200 rounded">
              <div className="text-[10px] text-slate-500 font-bold uppercase">INTERMEDIATE STATIONS</div>
              <div className="font-bold text-blue-800 text-sm mt-0.5 font-mono">
                {routeData.intermediate_stations_count !== undefined ? routeData.intermediate_stations_count : Math.max(0, stations.length - 2)}
              </div>
              <div className="text-[9px] text-blue-600 mt-0.5">Halts / Junctions</div>
            </div>

            {/* ROUTE STATUS */}
            <div className="bg-slate-50 p-2 border border-slate-200 rounded">
              <div className="text-[10px] text-slate-500 font-bold uppercase">ROUTE STATUS</div>
              <div className="font-bold text-emerald-600 text-sm mt-0.5 flex items-center gap-1">
                <ShieldCheck className="w-4 h-4 text-emerald-600" />
                <span>{routeData.status || 'VALID'}</span>
              </div>
              <div className="text-[9px] text-slate-500 mt-0.5">Network Verified</div>
            </div>
          </div>

          {/* Sequential Station Progression Timeline */}
          {stations.length > 0 && (
            <div className="pt-2 border-t border-slate-200">
              <div className="text-[10px] font-bold text-slate-500 uppercase mb-1.5 flex items-center justify-between">
                <span>Network Sequence & Intermediate Halts:</span>
                <span className="font-mono text-[9px] text-slate-400">Total Stations: {stations.length}</span>
              </div>
              <div className="flex items-center gap-1 overflow-x-auto pb-1 text-[11px] scrollbar-thin">
                {stations.map((stn, idx) => {
                  const isFirst = idx === 0;
                  const isLast = idx === stations.length - 1;
                  return (
                    <React.Fragment key={stn.code || idx}>
                      {idx > 0 && (
                        <div className="text-slate-300 font-mono text-xs flex-shrink-0">→</div>
                      )}
                      <div className={`px-2 py-1 rounded flex-shrink-0 border flex flex-col items-center ${isFirst ? 'bg-emerald-50 border-emerald-300 text-emerald-900 font-bold' :
                        isLast ? 'bg-red-50 border-red-300 text-red-900 font-bold' :
                          'bg-white border-slate-200 text-slate-800'
                        }`}>
                        <div className="flex items-center gap-1">
                          <span className="font-mono">{stn.code || stn.station_code}</span>
                          {(stn.name || stn.station_name) && (
                            <span className="text-[9px] text-slate-500 font-normal">({stn.name || stn.station_name})</span>
                          )}
                        </div>
                        {stn.distance_km !== undefined && (
                          <span className="text-[9px] font-mono text-slate-400">{stn.distance_km} km</span>
                        )}
                      </div>
                    </React.Fragment>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* GIS Map */}
      <RailwayMap
        stations={stations}
        sections={sections}
        movements={movements}
        routePolyline={routePolyline}
        routeGeometry={routeData?.geometry}
        corridorName={selectedCorridorName}
        loading={routeLoading || (loading && stations.length === 0)}
        routeError={routeError}
        noRouteFound={noRouteFound}
        startStationDisplay={startStationDisplay || (startCode ? `${startCode}` : '')}
        endStationDisplay={endStationDisplay || (endCode ? `${endCode}` : '')}
        hasSelectedStations={Boolean(startCode && endCode)}
      />

      {/* Train Movement Table */}
      <div className="cris-panel overflow-hidden shadow-sm">
        <div className="cris-panel-header flex items-center justify-between">
          <span>LIVE TRAIN MOVEMENT TELEMETRY & SECTION MAPPING CONFIDENCE</span>
          <span className="text-[10px] text-slate-500 font-mono">
            {movements.length > 0
              ? `${movements.length} Candidate Trains (${corridorSummary.liveCount} Live Telemetry)`
              : '0 Candidate Trains'}
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="cris-table">
            <thead>
              <tr>
                <th>TRAIN</th>
                <th>NAME</th>
                <th>TYPE</th>
                <th>SCHEDULED</th>
                <th>LIVE STATUS</th>
                <th>LOCATION / SECTION</th>
                <th>SPEED</th>
                <th>DELAY</th>
                <th>MAPPING CONFIDENCE</th>
                <th>SOURCE</th>
                <th>UPDATED</th>
              </tr>
            </thead>
            <tbody>
              {loading && movements.length === 0 ? (
                <tr>
                  <td colSpan="11" className="text-center py-8 text-slate-500 italic">
                    Fetching live telemetry and candidate timetable...
                  </td>
                </tr>
              ) : !selectedCorridorId && !startCode ? (
                <tr>
                  <td colSpan="11" className="text-center py-12 text-slate-500">
                    <div className="flex flex-col items-center justify-center space-y-1">
                      <Layers className="w-8 h-8 text-slate-400 mb-1" />
                      <div className="font-bold text-slate-700 text-sm">NO CORRIDOR SELECTED</div>
                      <div className="text-xs text-slate-400 max-w-md text-center">
                        Please select a railway corridor or enter start & end station codes above to track candidate and live trains.
                      </div>
                    </div>
                  </td>
                </tr>
              ) : movements.length === 0 ? (
                <tr>
                  <td colSpan="11" className="text-center py-12 text-slate-500">
                    <div className="flex flex-col items-center justify-center space-y-1">
                      <AlertCircle className="w-8 h-8 text-slate-400 mb-1" />
                      <div className="font-bold text-slate-700 text-sm">No candidate trains scheduled today</div>
                      <div className="text-xs text-slate-400 max-w-md text-center">
                        No trains are scheduled to traverse the selected corridor sections on this journey date.
                      </div>
                    </div>
                  </td>
                </tr>
              ) : (
                movements.map((m) => {
                  const conf = m.mapping_confidence_pct || (typeof m.mapping_confidence === 'number' ? Math.round(m.mapping_confidence > 1 ? m.mapping_confidence : m.mapping_confidence * 100) : 95);
                  const barColor = conf >= 90 ? 'bg-emerald-600' : conf >= 75 ? 'bg-blue-600' : 'bg-amber-500';

                  return (
                    <tr key={m.train_number} className="hover:bg-slate-50 transition-colors">
                      <td className="font-mono font-bold text-slate-900 whitespace-nowrap">
                        <span className="text-blue-900">{m.train_number}</span>
                        {m.direction && (
                          <span className={`ml-1.5 px-1 py-0.2 text-[9px] font-mono font-bold rounded ${m.direction === 'DOWN' ? 'bg-indigo-100 text-indigo-800' : 'bg-purple-100 text-purple-800'}`}>
                            {m.direction}
                          </span>
                        )}
                      </td>
                      <td className="font-bold text-slate-800">
                        <div>{m.train_name}</div>
                        {(m.source_code || m.destination_code) && (
                          <div className="text-[10px] text-slate-500 font-mono font-normal">
                            {m.source_code || '—'} → {m.destination_code || '—'}
                          </div>
                        )}
                      </td>
                      <td>
                        <span className={`px-1.5 py-0.5 text-[10px] font-mono font-bold rounded border ${
                          m.train_type === 'VANDE_BHARAT' ? 'bg-sky-100 text-sky-800 border-sky-300' :
                          m.train_type === 'SUPERFAST' ? 'bg-blue-100 text-blue-800 border-blue-300' :
                          m.train_type === 'PASSENGER' || m.train_type === 'MEMU' ? 'bg-emerald-100 text-emerald-800 border-emerald-300' :
                          'bg-slate-100 text-slate-800 border-slate-300'
                        }`}>
                          {m.train_type || 'EXPRESS'}
                        </span>
                      </td>
                      <td>
                        <div className="font-semibold text-slate-700 text-[11px]">{m.scheduled || 'Scheduled Today'}</div>
                        {m.scheduled_entry && m.scheduled_entry !== '—' && (
                          <div className="text-[10px] text-slate-500 font-mono">
                            {m.scheduled_entry} → {m.scheduled_exit}
                          </div>
                        )}
                      </td>
                      <td>
                        {m.is_live ? (
                          <span className="bg-emerald-100 text-emerald-800 border border-emerald-400 px-1.5 py-0.5 text-[10px] font-mono font-bold rounded flex items-center gap-1 w-fit">
                            <Radio className="w-2.5 h-2.5 text-emerald-600 animate-pulse" />
                            {m.live_status || m.status || 'RUNNING'}
                          </span>
                        ) : m.is_stale ? (
                          <span className="bg-amber-100 text-amber-800 border border-amber-400 px-1.5 py-0.5 text-[10px] font-mono font-bold rounded flex items-center gap-1 w-fit">
                            <Clock className="w-2.5 h-2.5 text-amber-600" />
                            STALE ({m.age_minutes ? `${m.age_minutes}m` : 'OLD'})
                          </span>
                        ) : (
                          <span className="bg-slate-100 text-slate-600 border border-slate-300 px-1.5 py-0.5 text-[10px] font-mono font-semibold rounded w-fit inline-block">
                            SCHEDULED — LIVE UNAVAILABLE
                          </span>
                        )}
                      </td>
                      <td>
                        <div className="font-bold text-[#134074]">{m.current_location || m.section_code || 'Section En Route'}</div>
                        {m.latitude && m.longitude && m.is_live ? (
                          <div className="font-mono text-[10px] text-emerald-700">
                            GPS: {Number(m.latitude).toFixed(3)}, {Number(m.longitude).toFixed(3)}
                          </div>
                        ) : (
                          <div className="font-mono text-[10px] text-slate-400 italic">No GPS Lock</div>
                        )}
                      </td>
                      <td className="font-mono font-bold">
                        {m.is_live && m.speed_kmh !== null && m.speed_kmh !== undefined ? (
                          <span className="text-slate-900">{m.speed_kmh} km/h</span>
                        ) : (
                          <span className="text-slate-400 font-bold">—</span>
                        )}
                      </td>
                      <td>
                        {m.is_live && m.delay_minutes !== null && m.delay_minutes !== undefined ? (
                          <span className={`px-1.5 py-0.5 text-[10px] font-mono font-bold rounded ${m.delay_minutes > 0 ? 'bg-red-600 text-white' : 'bg-emerald-600 text-white'}`}>
                            {m.delay_minutes > 0 ? `+${m.delay_minutes} min` : 'RIGHT TIME'}
                          </span>
                        ) : (
                          <span className="font-mono text-slate-400 font-bold">—</span>
                        )}
                      </td>
                      <td>
                        <div className="space-y-0.5" title={m.mapping_reason || ''}>
                          <div className="flex items-center space-x-1.5">
                            <span className="font-mono font-bold text-slate-800 text-[11px]">{conf}%</span>
                            <div className="w-12 h-1.5 bg-slate-200 rounded-xs overflow-hidden">
                              <div className={`h-full ${barColor}`} style={{ width: `${conf}%` }} />
                            </div>
                          </div>
                          <div className="text-[9px] text-slate-500 font-mono truncate max-w-[130px]">
                            {m.mapping_method || (conf >= 90 ? 'EXACT_ROUTE_SECTION_MATCH' : 'PARTIAL_ROUTE_MATCH')}
                          </div>
                        </div>
                      </td>
                      <td className="font-mono text-[10px] font-bold text-slate-700">
                        {m.source || 'Timetable Master'}
                      </td>
                      <td className="font-mono text-[10px] text-slate-500">
                        {m.last_updated && m.last_updated !== '—' ? m.last_updated : '—'}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
