'use client';

import { useState } from 'react';
import { ExternalLink, RefreshCw, Smartphone, Store, Bike, Headset, Shield, Info } from 'lucide-react';

const portals = [
  { id: 'customer', name: 'Customer App', path: '/customer', icon: Smartphone, defaultRole: 'customer1 / 1234' },
  { id: 'courier', name: 'Courier Portal', path: '/courier', icon: Bike, defaultRole: 'courier1 / 1234' },
  { id: 'partner', name: 'Partner Restaurant', path: '/partner', icon: Store, defaultRole: 'laplacinte / 1234' },
  { id: 'support', name: 'Support Desk', path: '/support', icon: Headset, defaultRole: 'support1 / 1234' },
  { id: 'admin', name: 'Admin Dashboard', path: '/admin', icon: Shield, defaultRole: 'admin / admin' },
];

export default function Home() {
  const [activePortal, setActivePortal] = useState('/customer');
  const [iframeKey, setIframeKey] = useState(0);
  const [showCreds, setShowCreds] = useState(false);

  const current = portals.find(p => p.path === activePortal) || portals[0];

  const handleRefresh = () => {
    setIframeKey(k => k + 1);
  };

  return (
    <div className="flex flex-col w-screen h-screen overflow-hidden bg-slate-950 text-slate-100 font-sans">
      {/* Top Header & Portal Switcher */}
      <header className="flex-none flex items-center justify-between px-3 py-2 bg-slate-900 border-b border-slate-800 text-sm z-30 shadow-md">
        <div className="flex items-center gap-2">
          {/* Logo */}
          <div className="flex items-center gap-2 pr-2 border-r border-slate-700">
            <div className="w-7 h-7 rounded-lg overflow-hidden bg-amber-500/20 flex items-center justify-center p-0.5">
              <img
                src="/static/logo.png"
                alt="Elyanivery"
                className="w-full h-full object-contain"
                onError={(e) => {
                  (e.currentTarget as HTMLElement).style.display = 'none';
                }}
              />
            </div>
            <span className="font-bold tracking-tight text-white hidden sm:inline">Elyanivery</span>
          </div>

          {/* Portal Switcher Buttons */}
          <nav className="flex items-center gap-1 overflow-x-auto py-0.5">
            {portals.map((p) => {
              const Icon = p.icon;
              const isActive = activePortal === p.path;
              return (
                <button
                  key={p.id}
                  id={`portal-btn-${p.id}`}
                  onClick={() => {
                    setActivePortal(p.path);
                    setIframeKey(k => k + 1);
                  }}
                  className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors cursor-pointer whitespace-nowrap ${
                    isActive
                      ? 'bg-amber-500 text-slate-950 font-semibold shadow-sm'
                      : 'text-slate-300 hover:text-white hover:bg-slate-800'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{p.name}</span>
                </button>
              );
            })}
          </nav>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2 pl-2">
          {/* Credentials Info Pill */}
          <div className="relative">
            <button
              id="creds-toggle-btn"
              onClick={() => setShowCreds(!showCreds)}
              className="flex items-center gap-1 px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 transition-colors"
              title="View Demo Credentials"
            >
              <Info className="w-3.5 h-3.5 text-amber-400" />
              <span className="hidden md:inline">Credentials:</span>
              <span className="font-mono text-[11px] text-amber-300 font-semibold">{current.defaultRole}</span>
            </button>

            {showCreds && (
              <div className="absolute right-0 top-8 w-72 bg-slate-900 border border-slate-700 rounded-lg p-3 shadow-xl text-xs space-y-2 z-50">
                <div className="font-semibold text-slate-200 border-b border-slate-700 pb-1 flex justify-between items-center">
                  <span>Demo Logins</span>
                  <button onClick={() => setShowCreds(false)} className="text-slate-400 hover:text-white">&times;</button>
                </div>
                <div className="space-y-1.5 font-mono text-[11px]">
                  <div className="flex justify-between"><span className="text-slate-400">Admin:</span> <span className="text-amber-300">admin / admin</span></div>
                  <div className="flex justify-between"><span className="text-slate-400">Customer:</span> <span className="text-amber-300">customer1 / 1234</span></div>
                  <div className="flex justify-between"><span className="text-slate-400">Courier:</span> <span className="text-amber-300">courier1 / 1234</span></div>
                  <div className="flex justify-between"><span className="text-slate-400">Partner:</span> <span className="text-amber-300">laplacinte / 1234</span></div>
                  <div className="flex justify-between"><span className="text-slate-400">Support:</span> <span className="text-amber-300">support1 / 1234</span></div>
                </div>
                <p className="text-[10px] text-slate-400 pt-1 border-t border-slate-800">
                  You can also register any new account directly in any portal.
                </p>
              </div>
            )}
          </div>

          {/* Reload Portal */}
          <button
            id="reload-portal-btn"
            onClick={handleRefresh}
            className="p-1.5 text-slate-300 hover:text-white hover:bg-slate-800 rounded transition-colors"
            title="Reload Active Portal"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>

          {/* Open in new tab */}
          <a
            id="open-tab-btn"
            href={activePortal}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 transition-colors"
            title="Open portal directly in a new browser tab"
          >
            <span className="hidden sm:inline">New Tab</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </header>

      {/* Main Fullscreen Iframe Viewport */}
      <main className="flex-1 w-full h-full relative bg-black">
        <iframe
          key={`${activePortal}-${iframeKey}`}
          id="portal-viewport-frame"
          src={activePortal}
          className="w-full h-full border-none m-0 p-0 block bg-slate-900"
          title={`Elyanivery ${current.name}`}
        />
      </main>
    </div>
  );
}
