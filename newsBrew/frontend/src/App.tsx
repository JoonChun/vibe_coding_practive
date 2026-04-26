import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './layouts/Layout';
import Dashboard from './pages/Dashboard';
import Keywords from './pages/Keywords';
import Archive from './pages/Archive';
import Settings from './pages/Settings';
import Help from './pages/Help';
import { LanguageProvider } from './contexts/LanguageContext';
import { BrewProvider } from './contexts/BrewContext';
import { ToastProvider } from './contexts/ToastContext';

function App() {
  return (
    <LanguageProvider>
    <ToastProvider>
    <BrewProvider>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/keywords" element={<Keywords />} />
            <Route path="/archive" element={<Archive />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/help" element={<Help />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </BrewProvider>
    </ToastProvider>
    </LanguageProvider>
  );
}

export default App;
