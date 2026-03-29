/**
 * CIPP/E Legal SaaS — Main React App
 * Entry point for Vite/React application
 */

import React from 'react';
import LegalResearchLab from './LegalResearchLab';
import './App.css';

const App: React.FC = () => {
  return (
    <div className="app">
      <LegalResearchLab />
    </div>
  );
};

export default App;
