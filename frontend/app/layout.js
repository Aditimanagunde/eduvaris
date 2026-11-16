// Required by Next.js. All the Eduvaris screens live in app/page.js.
export const metadata = {
  title: "Eduvaris",
  description: "APAAR ID-based student data management and verification for AICTE-approved institutions",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, background: "#0f141c" }}>{children}</body>
    </html>
  );
}