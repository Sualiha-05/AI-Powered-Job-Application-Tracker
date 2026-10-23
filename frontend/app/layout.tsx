import type { ReactNode } from 'react';
import './globals.css';

export const metadata = {
  title: 'Job Tracker',
  description: 'Track applications and see how well your resume matches each role.',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
