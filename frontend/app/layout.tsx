import type { ReactNode } from 'react';
import { Bricolage_Grotesque, Instrument_Sans } from 'next/font/google';
import './globals.css';

const display = Bricolage_Grotesque({ subsets: ['latin'], variable: '--f-display', display: 'swap' });
const body = Instrument_Sans({ subsets: ['latin'], variable: '--f-body', display: 'swap' });

export const metadata = {
  title: 'Job Tracker',
  description: 'Track applications and see how well your resume matches each role.',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className={`${display.variable} ${body.variable}`}>{children}</body>
    </html>
  );
}
