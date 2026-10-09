import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const userAgent = request.headers.get('user-agent') || '';
  const pathname = request.nextUrl.pathname;
  const isCli = /curl|wget|httpie|fetch|powershell/i.test(userAgent);

  // If curl/wget requests root, or user requests /install or /install.sh directly
  if ((pathname === '/' && isCli) || pathname === '/install' || pathname === '/install.sh') {
    return NextResponse.rewrite(new URL('/api/install', request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/', '/install', '/install.sh'],
};
