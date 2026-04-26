import { createContext, useContext, useState, useCallback, ReactNode } from 'react';

type ToastType = 'success' | 'error' | 'info';

interface Toast {
  id: number;
  type: ToastType;
  message: string;
  sub?: string;
}

interface ToastContextValue {
  showToast: (type: ToastType, message: string, sub?: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export const useToast = () => {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be inside ToastProvider');
  return ctx;
};

const ICONS: Record<ToastType, string> = {
  success: 'check_circle',
  error: 'error',
  info: 'info',
};

const STYLES: Record<ToastType, string> = {
  success: 'bg-[#1a2e1a] border-[#a3e635]/30 text-[#a3e635]',
  error: 'bg-[#2e1a1a] border-red-400/30 text-red-400',
  info: 'bg-surface-container-high border-outline-variant/30 text-on-surface',
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  let counter = 0;

  const showToast = useCallback((type: ToastType, message: string, sub?: string) => {
    const id = ++counter;
    setToasts(prev => [...prev, { id, type, message, sub }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 3500);
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="fixed bottom-8 right-8 z-50 flex flex-col gap-3 pointer-events-none">
        {toasts.map(toast => (
          <div
            key={toast.id}
            className={`flex items-center gap-3 px-5 py-4 rounded-2xl border shadow-2xl pointer-events-auto animate-in slide-in-from-bottom-4 duration-300 ${STYLES[toast.type]}`}
          >
            <span className="material-symbols-outlined text-[20px]" style={{ fontVariationSettings: "'FILL' 1" }}>
              {ICONS[toast.type]}
            </span>
            <div>
              <p className="font-label font-bold text-sm">{toast.message}</p>
              {toast.sub && <p className="font-body text-xs opacity-70 mt-0.5">{toast.sub}</p>}
            </div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
