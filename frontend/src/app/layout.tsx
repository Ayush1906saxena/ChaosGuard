import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import QueryProvider from '@/components/QueryProvider';
import Toaster from '@/components/Toaster';
import ErrorBoundary from '@/components/ErrorBoundary';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
});

export const metadata: Metadata = {
  title: 'ChaosGuard AI - Autonomous Security Platform',
  description: 'AI-powered multi-agent security scanning and chaos engineering platform',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-[#050507] text-zinc-100 antialiased`}>
        {/* Ambient gradient mesh */}
        <div className="gradient-mesh" aria-hidden="true" />

        {/* Noise overlay */}
        <div className="noise-overlay" aria-hidden="true" />

        {/* Main content above overlays */}
        <div className="relative z-10">
          <ErrorBoundary>
            <QueryProvider>
              {children}
              <Toaster />
            </QueryProvider>
          </ErrorBoundary>
        </div>
      </body>
    </html>
  );
}
