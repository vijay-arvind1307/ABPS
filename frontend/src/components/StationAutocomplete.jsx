import React, { useState, useEffect, useRef } from 'react';
import { Search, MapPin, Check, X, Loader2, Train } from 'lucide-react';
import { searchStationsV2, getStationMaster } from '../services/api';

const POPULAR_TN_STATIONS = [
  { code: 'MAS', name: 'Chennai Central', division: 'MAS', state: 'Tamil Nadu', category: 'NSG-1' },
  { code: 'MS', name: 'Chennai Egmore', division: 'MAS', state: 'Tamil Nadu', category: 'NSG-2' },
  { code: 'TBM', name: 'Tambaram', division: 'MAS', state: 'Tamil Nadu', category: 'NSG-2' },
  { code: 'CGL', name: 'Chengalpattu Jn', division: 'MAS', state: 'Tamil Nadu', category: 'NSG-3' },
  { code: 'TPJ', name: 'Tiruchchirappalli Jn', division: 'TPJ', state: 'Tamil Nadu', category: 'NSG-2' },
  { code: 'MDU', name: 'Madurai Jn', division: 'MDU', state: 'Tamil Nadu', category: 'NSG-2' },
  { code: 'CVP', name: 'Kovilpatti', division: 'MDU', state: 'Tamil Nadu', category: 'NSG-4' },
  { code: 'TEN', name: 'Tirunelveli Jn', division: 'TVC', state: 'Tamil Nadu', category: 'NSG-3' },
  { code: 'CBE', name: 'Coimbatore Jn', division: 'SA', state: 'Tamil Nadu', category: 'NSG-2' },
  { code: 'SA', name: 'Salem Jn', division: 'SA', state: 'Tamil Nadu', category: 'NSG-3' },
  { code: 'ED', name: 'Erode Jn', division: 'SA', state: 'Tamil Nadu', category: 'NSG-3' },
  { code: 'RMM', name: 'Rameswaram', division: 'MDU', state: 'Tamil Nadu', category: 'NSG-4' }
];

export default function StationAutocomplete({
  value,
  onChange,
  placeholder = 'Search station code or name...',
  label,
  id,
  stateFilter = '',
  required = false,
  disabled = false,
  className = ''
}) {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedStation, setSelectedStation] = useState(null);
  const [options, setOptions] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);

  const containerRef = useRef(null);
  const inputRef = useRef(null);
  const debounceRef = useRef(null);

  // Sync internal search input with incoming prop value
  useEffect(() => {
    if (!value) {
      setSelectedStation(null);
      setSearchTerm('');
      return;
    }

    // If value matches current selected station code, don't re-fetch
    if (selectedStation && selectedStation.code === value) {
      return;
    }

    // Resolve station details from backend
    let active = true;
    getStationMaster(value)
      .then((res) => {
        if (active && res.data && res.data.station) {
          const stn = res.data.station;
          setSelectedStation(stn);
          setSearchTerm(`${stn.code} - ${stn.name}`);
        }
      })
      .catch(() => {
        if (active) {
          setSearchTerm(value);
        }
      });

    return () => {
      active = false;
    };
  }, [value]);

  // Handle outside clicks to close dropdown
  useEffect(() => {
    function handleClickOutside(event) {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setIsOpen(false);
        // If nothing selected, restore previous selected or clear
        if (selectedStation) {
          setSearchTerm(`${selectedStation.code} - ${selectedStation.name}`);
        } else if (value) {
          setSearchTerm(value);
        } else {
          setSearchTerm('');
        }
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [selectedStation, value]);

  // Debounced search query
  const performSearch = (query) => {
    if (!query || query.trim().length === 0) {
      setOptions(POPULAR_TN_STATIONS);
      setLoading(false);
      return;
    }

    setLoading(true);
    searchStationsV2(query.trim(), stateFilter, 25)
      .then((res) => {
        const results = Array.isArray(res.data) ? res.data : (res.data?.results || []);
        setOptions(results);
        setHighlightedIndex(results.length > 0 ? 0 : -1);
      })
      .catch((err) => {
        console.error('Failed to search stations:', err);
        setOptions([]);
      })
      .finally(() => {
        setLoading(false);
      });
  };

  const handleInputChange = (e) => {
    const text = e.target.value;
    setSearchTerm(text);
    setIsOpen(true);

    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    debounceRef.current = setTimeout(() => {
      performSearch(text);
    }, 220);
  };

  const handleFocus = () => {
    if (disabled) return;
    setIsOpen(true);
    if (!searchTerm || searchTerm.includes(' - ')) {
      // Show popular stations or trigger search if short
      setOptions(POPULAR_TN_STATIONS);
      setHighlightedIndex(-1);
    } else {
      performSearch(searchTerm);
    }
  };

  const handleSelect = (station) => {
    setSelectedStation(station);
    setSearchTerm(`${station.code} - ${station.name}`);
    setIsOpen(false);
    if (onChange) {
      onChange(station.code, station);
    }
  };

  const handleClear = (e) => {
    e.stopPropagation();
    setSelectedStation(null);
    setSearchTerm('');
    setOptions(POPULAR_TN_STATIONS);
    if (onChange) {
      onChange('', null);
    }
    if (inputRef.current) {
      inputRef.current.focus();
    }
  };

  const handleKeyDown = (e) => {
    if (!isOpen) {
      if (e.key === 'ArrowDown' || e.key === 'Enter') {
        setIsOpen(true);
        handleFocus();
      }
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightedIndex((prev) => (prev < options.length - 1 ? prev + 1 : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : options.length - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (highlightedIndex >= 0 && highlightedIndex < options.length) {
        handleSelect(options[highlightedIndex]);
      } else if (options.length > 0) {
        handleSelect(options[0]);
      }
    } else if (e.key === 'Escape') {
      setIsOpen(false);
    }
  };

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      {label && (
        <label htmlFor={id} className="block text-xs font-semibold text-slate-700 mb-1">
          {label} {required && <span className="text-red-500">*</span>}
        </label>
      )}

      <div className="relative">
        <div className="absolute inset-y-0 left-0 pl-2.5 flex items-center pointer-events-none text-slate-400">
          {loading ? (
            <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
          ) : (
            <Train className="w-4 h-4 text-slate-400" />
          )}
        </div>

        <input
          ref={inputRef}
          id={id}
          type="text"
          value={searchTerm}
          onChange={handleInputChange}
          onFocus={handleFocus}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          autoComplete="off"
          className="w-full pl-8 pr-8 py-1.5 text-xs bg-white border border-slate-300 rounded focus:ring-1 focus:ring-blue-500 focus:border-blue-500 font-medium text-slate-800 placeholder-slate-400 shadow-sm transition-all"
        />

        {searchTerm && !disabled && (
          <button
            type="button"
            onClick={handleClear}
            className="absolute inset-y-0 right-0 pr-2.5 flex items-center text-slate-400 hover:text-slate-600"
            title="Clear station"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Autocomplete Dropdown */}
      {isOpen && !disabled && (
        <div className="absolute z-50 mt-1 w-full max-h-64 bg-white border border-slate-200 rounded-md shadow-xl overflow-y-auto text-xs divide-y divide-slate-100 animate-in fade-in slide-in-from-top-1 duration-150">
          <div className="px-2.5 py-1 bg-slate-50 border-b border-slate-100 flex items-center justify-between text-[10px] font-semibold text-slate-500">
            <span>
              {searchTerm && !searchTerm.includes(' - ')
                ? `Search results (${options.length})`
                : 'Frequent Stations (Southern Railway)'}
            </span>
            <span className="text-[9px] text-blue-700 bg-blue-50 px-1 rounded">
              Authoritative Master: 726 Stations
            </span>
          </div>

          {options.length === 0 ? (
            <div className="p-3 text-center text-slate-400 italic">
              No matching stations found in Southern Railway Master.
            </div>
          ) : (
            options.map((stn, idx) => {
              const isSelected = selectedStation && selectedStation.code === stn.code;
              const isHighlighted = idx === highlightedIndex;

              return (
                <div
                  key={stn.code}
                  onMouseDown={() => handleSelect(stn)}
                  onMouseEnter={() => setHighlightedIndex(idx)}
                  className={`px-3 py-2 cursor-pointer flex items-center justify-between transition-colors ${
                    isSelected
                      ? 'bg-blue-50 text-blue-900 font-semibold'
                      : isHighlighted
                      ? 'bg-slate-100 text-slate-900'
                      : 'hover:bg-slate-50 text-slate-700'
                  }`}
                >
                  <div className="flex items-center space-x-2">
                    <span className="inline-flex items-center justify-center font-mono font-bold px-1.5 py-0.5 text-[11px] rounded bg-blue-100 text-blue-800 border border-blue-200 min-w-[42px] text-center">
                      {stn.code}
                    </span>
                    <div>
                      <div className="font-semibold text-slate-800">
                        {stn.name}
                      </div>
                      <div className="text-[10px] text-slate-500 flex items-center space-x-2">
                        <span>Div: <strong className="text-slate-700">{stn.division}</strong></span>
                        <span>•</span>
                        <span>{stn.state}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-1.5 text-[10px]">
                    {stn.category && (
                      <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200 font-mono text-[9px]">
                        {stn.category}
                      </span>
                    )}
                    {isSelected && <Check className="w-3.5 h-3.5 text-blue-600" />}
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
