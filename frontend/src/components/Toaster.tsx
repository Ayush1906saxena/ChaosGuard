'use client';

import { Toaster as SonnerToaster } from 'sonner';

export default function Toaster() {
  return (
    <SonnerToaster
      theme="dark"
      position="bottom-right"
      toastOptions={{
        style: {
          background: 'rgba(24, 24, 27, 0.9)',
          border: '1px solid rgba(255, 255, 255, 0.06)',
          color: '#e4e4e7',
          backdropFilter: 'blur(12px)',
        },
      }}
    />
  );
}
