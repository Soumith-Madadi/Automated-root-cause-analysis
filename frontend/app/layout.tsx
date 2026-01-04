import './globals.css'

export const metadata = {
  title: 'RCA System',
  description: 'Production-Grade Root Cause Analysis System',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}


