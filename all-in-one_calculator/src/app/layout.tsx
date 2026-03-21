import type { Metadata } from "next";
import localFont from "next/font/local";
import { JetBrains_Mono } from "next/font/google";
import { Sidebar } from "@/components/layout/sidebar";
import { MobileNav } from "@/components/layout/mobile-nav";
import "./globals.css";

const pretendard = localFont({
  src: "../../public/fonts/PretendardVariable.woff2",
  variable: "--font-sans",
  display: "swap",
  weight: "45 920",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "올인원 라이프 계산기",
  description:
    "복리, 대출, 연봉, 단위 변환, 디데이 등 실생활 계산을 한곳에서.",
  manifest: "/manifest.json",
  themeColor: "#0f172a",
  openGraph: {
    title: "올인원 라이프 계산기",
    description:
      "복리, 대출, 연봉, 단위 변환, 디데이 등 실생활 계산을 한곳에서. 개인정보 걱정 없이 브라우저에서 바로 사용하세요.",
    type: "website",
    locale: "ko_KR",
    siteName: "Life Calc",
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Life Calc",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className={`${pretendard.variable} ${jetbrainsMono.variable} dark h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <Sidebar />
        <div className="lg:pl-60 flex flex-col flex-1">
          <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8 pb-20 lg:pb-6">
            {children}
          </main>
          <footer className="hidden lg:block px-6 py-3 text-xs text-muted-foreground border-t border-border">
            본 계산기는 참고용이며, 실제 금융기관 계산과 차이가 있을 수 있습니다.
          </footer>
        </div>
        <MobileNav />
      </body>
    </html>
  );
}
