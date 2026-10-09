import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const host = request.headers.get('host') || '';
  const userAgent = request.headers.get('user-agent') || '';
  const pathname = request.nextUrl.pathname;
  const search = request.nextUrl.search;
  const isCli = /curl|wget|httpie|fetch|powershell/i.test(userAgent);

  // 1. Host Redirection (Canonical Domain Enforcement)
  // 308 Permanent Redirect for agy-skills.com, www.agy-skills.com, and www.agy-skills.sh -> https://agy-skills.sh
  const isSecondaryDomain =
    host.includes('agy-skills.com') ||
    host.startsWith('www.agy-skills.sh') ||
    host.startsWith('www.agy-skills.com');

  if (isSecondaryDomain) {
    const targetUrl = new URL(`https://agy-skills.sh${pathname}${search}`);
    return NextResponse.redirect(targetUrl, 308);
  }

  // 2. Installer delivery for CLI / terminal requests on agy-skills.sh
  if ((pathname === '/' && isCli) || pathname === '/install' || pathname === '/install.sh') {
    return NextResponse.rewrite(new URL('/api/install', request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};
