import type { ReactNode } from 'react';
import { useLocation, Link } from 'react-router-dom';
import { useLanguage } from '../contexts/LanguageContext';

const Layout = ({ children }: { children: ReactNode }) => {
  const location = useLocation();
  const currentPath = location.pathname;
  const { language, setLanguage, t } = useLanguage();

  const common = t.common;

  return (
    <div className="bg-background text-on-background min-h-screen flex flex-col md:flex-row antialiased font-body">
      
      {/* SideNavBar (Hidden on Mobile, Visible on Desktop) */}
      <nav className="hidden md:flex flex-col p-4 gap-2 h-screen w-64 border-r border-transparent bg-surface-container-low dark:bg-primary-container/20 sticky top-0 shrink-0">
        <div className="mb-8 px-4 mt-4 flex items-center gap-3">
          <img src="/newsbrew_logo.jpg" alt="News Brew Logo" className="w-10 h-10 object-contain rounded-md" />
          <h1 className="text-xl font-black text-primary tracking-tighter italic font-headline">{common.newsBrew}</h1>
        </div>
        
        <div className="flex items-center gap-3 px-4 mb-8">
          <div className="w-10 h-10 rounded-full bg-surface-container-high overflow-hidden">
            <span className="material-symbols-outlined text-4xl text-outline mt-1 text-center w-full block">account_circle</span>
          </div>
          <div>
            <p className="font-headline font-bold text-sm text-primary">{common.brewMaster}</p>
            <p className="font-body text-xs text-on-surface-variant flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-tertiary-fixed-dim inline-block"></span> {common.automationActive}
            </p>
          </div>
        </div>

        <div className="flex-1 flex flex-col gap-2">
          <Link to="/" className={`flex items-center gap-3 px-4 py-3 rounded-lg font-headline text-sm font-medium transition-transform ease-out duration-300 hover:translate-x-1 ${currentPath === '/' ? 'bg-primary-container text-on-primary shadow-lg shadow-primary-container/20' : 'text-primary hover:bg-primary-container/5'}`}>
            <span className="material-symbols-outlined" style={{ fontVariationSettings: currentPath === '/' ? "'FILL' 1" : "'FILL' 0" }}>dashboard</span>
            {common.dashboard}
          </Link>
          <Link to="/keywords" className={`flex items-center gap-3 px-4 py-3 rounded-lg font-headline text-sm font-medium transition-transform ease-out duration-300 hover:translate-x-1 ${currentPath.includes('/keywords') ? 'bg-primary-container text-on-primary shadow-lg shadow-primary-container/20' : 'text-primary hover:bg-primary-container/5'}`}>
            <span className="material-symbols-outlined" style={{ fontVariationSettings: currentPath.includes('/keywords') ? "'FILL' 1" : "'FILL' 0" }}>temp_preferences_custom</span>
            {common.keywords}
          </Link>
          <Link to="/archive" className={`flex items-center gap-3 px-4 py-3 rounded-lg font-headline text-sm font-medium transition-transform ease-out duration-300 hover:translate-x-1 ${currentPath.includes('/archive') ? 'bg-primary-container text-on-primary shadow-lg shadow-primary-container/20' : 'text-primary hover:bg-primary-container/5'}`}>
            <span className="material-symbols-outlined" style={{ fontVariationSettings: currentPath.includes('/archive') ? "'FILL' 1" : "'FILL' 0" }}>auto_stories</span>
            {common.archive}
          </Link>
          <Link to="/settings" className={`flex items-center gap-3 px-4 py-3 rounded-lg font-headline text-sm font-medium transition-transform ease-out duration-300 hover:translate-x-1 ${currentPath.includes('/settings') ? 'bg-primary-container text-on-primary shadow-lg shadow-primary-container/20' : 'text-primary hover:bg-primary-container/5'}`}>
            <span className="material-symbols-outlined" style={{ fontVariationSettings: currentPath.includes('/settings') ? "'FILL' 1" : "'FILL' 0" }}>settings</span>
            {common.settings}
          </Link>
        </div>

        <div className="mt-auto flex flex-col gap-2 pt-4 border-t border-outline-variant/15">
          <button className="w-full py-3 px-4 bg-tertiary-container text-on-primary rounded-xl font-headline font-bold text-sm shadow-md hover:bg-primary transition-colors flex items-center justify-center gap-2">
            <span className="material-symbols-outlined text-[18px]">play_arrow</span>
            {common.startBrewing}
          </button>
          <div className="mt-4 flex flex-col gap-1">
            <Link
              to="/help"
              className={`flex items-center w-full gap-3 px-4 py-2 rounded-lg font-body text-sm hover:translate-x-1 transition-transform ease-out duration-300 ${
                currentPath.includes('/help')
                  ? 'bg-primary-container/10 text-primary'
                  : 'text-on-surface-variant hover:bg-primary-container/5'
              }`}
            >
              <span className="material-symbols-outlined text-[18px]">help</span>
              {common.help}
            </Link>
            <button className="flex items-center w-full gap-3 px-4 py-2 text-on-surface-variant hover:bg-primary-container/5 rounded-lg font-body text-sm hover:translate-x-1 transition-transform ease-out duration-300">
              <span className="material-symbols-outlined text-[18px]">logout</span>
              {common.logout}
            </button>
          </div>
        </div>
      </nav>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col relative h-screen overflow-hidden">
        
        {/* Top Header Controls (Language Switcher) */}
        <header className="absolute top-0 right-0 z-50 p-4 md:p-6 flex items-center gap-4">
          <div className="bg-surface-container-high/50 backdrop-blur-md px-1.5 py-1 rounded-xl border border-outline-variant/10 shadow-sm flex items-center gap-1">
            <button 
              onClick={() => setLanguage('ko')}
              className={`px-3 py-1.5 rounded-lg text-xs font-label font-bold transition-all ${language === 'ko' ? 'bg-primary text-on-primary shadow-sm' : 'text-on-surface-variant hover:bg-primary/5'}`}
            >
              KR
            </button>
            <button 
              onClick={() => setLanguage('en')}
              className={`px-3 py-1.5 rounded-lg text-xs font-label font-bold transition-all ${language === 'en' ? 'bg-primary text-on-primary shadow-sm' : 'text-on-surface-variant hover:bg-primary/5'}`}
            >
              EN
            </button>
          </div>
        </header>

        {/* Mobile TopAppBar */}
        <header className="md:hidden sticky top-0 left-0 w-full z-40 bg-background/80 backdrop-blur-xl border-b border-primary/5 shadow-sm shadow-primary/5 flex justify-between items-center h-16 px-6 shrink-0">
          <div className="text-2xl font-extrabold text-primary tracking-tighter italic font-headline flex items-center gap-2">
            <img src="/newsbrew_logo.jpg" alt="Logo" className="h-8 w-auto rounded" />
            {common.newsBrew}
          </div>
          <div className="flex items-center gap-2 text-primary">
            <button className="hover:bg-primary-container/5 transition-colors p-2 rounded-full active:scale-95 duration-200">
              <span className="material-symbols-outlined">account_circle</span>
            </button>
          </div>
        </header>

        {/* Dynamic Route Content */}
        <main className="flex-1 w-full overflow-y-auto pt-4 md:pt-0">
          {children}
        </main>
      </div>

      {/* BottomNavBar (Mobile Only) */}
      <nav className="md:hidden fixed bottom-0 left-0 w-full z-50 flex justify-around items-center px-4 py-3 pb-8 bg-background/90 backdrop-blur-md border-t border-primary/5 shadow-[0_-8px_30px_rgb(51,33,13,0.05)] font-headline text-[10px] uppercase tracking-widest shrink-0">
        <Link to="/" className={`flex flex-col items-center justify-center p-2 px-4 rounded-xl transition-colors ${currentPath === '/' ? 'text-on-tertiary-container bg-primary-container/5' : 'text-primary/60 hover:text-on-tertiary-container'}`}>
          <span className="material-symbols-outlined mb-1" style={{ fontVariationSettings: currentPath === '/' ? "'FILL' 1" : "'FILL' 0" }}>home</span>
          {common.dashboard}
        </Link>
        <Link to="/keywords" className={`flex flex-col items-center justify-center p-2 px-4 rounded-xl transition-colors ${currentPath.includes('/keywords') ? 'text-on-tertiary-container bg-primary-container/5' : 'text-primary/60 hover:text-on-tertiary-container'}`}>
          <span className="material-symbols-outlined mb-1" style={{ fontVariationSettings: currentPath.includes('/keywords') ? "'FILL' 1" : "'FILL' 0" }}>key</span>
          {common.keywords}
        </Link>
        <Link to="/archive" className={`flex flex-col items-center justify-center p-2 px-4 rounded-xl transition-colors ${currentPath.includes('/archive') ? 'text-on-tertiary-container bg-primary-container/5' : 'text-primary/60 hover:text-on-tertiary-container'}`}>
          <span className="material-symbols-outlined mb-1" style={{ fontVariationSettings: currentPath.includes('/archive') ? "'FILL' 1" : "'FILL' 0" }}>history</span>
          {common.archive}
        </Link>
        <Link to="/settings" className={`flex flex-col items-center justify-center p-2 px-4 rounded-xl transition-colors ${currentPath.includes('/settings') ? 'text-on-tertiary-container bg-primary-container/5' : 'text-primary/60 hover:text-on-tertiary-container'}`}>
          <span className="material-symbols-outlined mb-1" style={{ fontVariationSettings: currentPath.includes('/settings') ? "'FILL' 1" : "'FILL' 0" }}>tune</span>
          {common.settings}
        </Link>
      </nav>
      
    </div>
  );
};

export default Layout;
