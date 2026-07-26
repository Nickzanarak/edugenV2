import type { Metadata } from "next";
import { QueryProvider } from "../src/components/providers/QueryProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "EduGen",
  description: "สรุปเนื้อหา สร้างข้อสอบ และถาม-ตอบจากเอกสาร",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
