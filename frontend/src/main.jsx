import React from 'react';
import ReactDOM from 'react-dom/client';
import SearchBox from './components/SearchBox';

const searchRoot = document.getElementById('react-live-search');
if (searchRoot) {
  ReactDOM.createRoot(searchRoot).render(
    <React.StrictMode>
      <SearchBox />
    </React.StrictMode>
  );
}