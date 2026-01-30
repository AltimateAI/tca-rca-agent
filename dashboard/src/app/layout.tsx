export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <head>
        <title>TCA RCA Agent</title>
      </head>
      <body>{children}</body>
    </html>
  )
}
