import type { Metadata } from "next";
import { QueryProvider } from "../src/components/providers/QueryProvider";
import { ToastProvider } from "../src/components/ui/Toast";
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
    <html lang="th">
      <body className="antialiased">
        <QueryProvider>
          <ToastProvider>{children}</ToastProvider>
        </QueryProvider>
      </body>
    </html>
  );
}