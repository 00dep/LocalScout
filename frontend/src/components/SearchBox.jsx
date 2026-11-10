import React, { useState, useEffect } from 'react';

// Custom Debounce Hook
function useDebounce(value, delay = 350) {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => clearTimeout(handler);
  }, [value, delay]);

  return debouncedValue;
}

export default function SearchBox() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  // Apply Debounce
  const debouncedQuery = useDebounce(query, 350);

  useEffect(() => {
    if (debouncedQuery.trim().length > 1) {
      setLoading(true);
      fetch(`/api/search/?q=${encodeURIComponent(debouncedQuery)}`)
        .then(res => res.json())
        .then(data => {
          setResults(data);
          setLoading(false);
        })
        .catch(() => setLoading(false));
    } else {
      setResults([]);
    }
  }, [debouncedQuery]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    if (query.trim()) {
      window.location.href = `/places/?q=${encodeURIComponent(query)}`;
    }
  };

  return (
    <div className="relative max-w-xl mx-auto my-6 text-left z-50">
      <form onSubmit={handleSearchSubmit} className="flex items-center bg-slate-800/90 border border-slate-700 p-2 rounded-2xl sm:rounded-full shadow-2xl backdrop-blur-md focus-within:border-purple-500 transition">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search for places, food, or landmarks..."
          className="w-full bg-transparent px-4 py-2.5 text-white placeholder-slate-400 text-sm focus:outline-none"
        />
        <button 
          type="submit" 
          className="bg-purple-600 hover:bg-purple-500 text-white font-semibold px-7 py-2.5 rounded-xl sm:rounded-full transition duration-200 shadow-lg shadow-purple-600/30 text-sm cursor-pointer whitespace-nowrap"
        >
          {loading ? 'Searching...' : 'Search'}
        </button>
      </form>
      
      {/* Dynamic Dropdown Suggestions */}
      {results.length > 0 && (
        <div className="absolute top-full left-0 right-0 bg-slate-800/95 border border-slate-700 rounded-2xl mt-2 overflow-hidden z-50 shadow-2xl backdrop-blur-xl">
          {results.map(place => (
            <a 
              key={place.id} 
              href={`/places/${place.id}/`} 
              className="flex justify-between items-center px-5 py-3 hover:bg-slate-700/80 text-white transition border-b border-slate-700/50 last:border-none"
            >
              <div>
                <p className="font-bold text-sm text-purple-300">{place.name}</p>
                <p className="text-xs text-slate-400">📍 {place.address}</p>
              </div>
              {place.category && (
                <span className="text-[10px] text-purple-300 bg-purple-950/60 border border-purple-800/40 px-2 py-0.5 rounded">
                  {place.category}
                </span>
              )}
            </a>
          ))}
        </div>
      )}
    </div>
  );
}