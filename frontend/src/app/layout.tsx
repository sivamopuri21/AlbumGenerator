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
        <header className="bg-white/80 backdrop-blur-md border-b border-gray-200/50 px-6 py-3 sticky top-0 z-40 shadow-sm">
          <div className="max-w-7xl mx-auto flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center shadow-md">
              <span className="text-white font-bold text-xs">LD</span>
            </div>
            <h1 className="text-lg font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
              LohanDigitals
            </h1>
          </div>
        </header>
        <main className="max-w-7xl mx-auto px-6 py-6">{children}</main>
      </body>
    </html>
  );
}
