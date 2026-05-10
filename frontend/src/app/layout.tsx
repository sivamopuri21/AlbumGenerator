import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LohanDigitals",
  description: "Generate beautiful photo albums",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <header className="bg-white border-b border-gray-200 px-6 py-4">
          <div className="max-w-6xl mx-auto flex items-center gap-3">
            <h1 className="text-xl font-semibold">LohanDigitals</h1>
          </div>
        </header>
        <main className="max-w-6xl mx-auto px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
