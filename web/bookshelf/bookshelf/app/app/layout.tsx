import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "本棚",
  description: "小さな書籍レビューサイト",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja">
      <body>
        <header className="site-header">
          <Link href="/" className="site-title">
            本棚
          </Link>
          <nav>
            <Link href="/books">書籍一覧</Link>
          </nav>
        </header>
        <main className="page-shell">{children}</main>
      </body>
    </html>
  );
}
