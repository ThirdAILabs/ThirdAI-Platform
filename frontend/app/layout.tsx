import './globals.css';

import { Analytics } from '@vercel/analytics/react';
import UserWrapper from './user_wrapper';

export const metadata = {
  title: 'ThirdAI Platform',
  description:
    'Democratize AI for everyone.',
};

export default function RootLayout({
  children
}: {
  children: React.ReactNode;
}) {

  return (
    <html lang="en">
      <body className="flex min-h-screen w-full flex-col bg-muted/40">
        <UserWrapper>
          {children}
        </UserWrapper>
      </body>
      <Analytics />
    </html>
  );
}
