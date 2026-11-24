import { NextResponse, type NextRequest } from "next/server";

import { REQUEST_PROTO_HEADER } from "./lib/cookie-policy";
import { SESSION_COOKIE } from "./lib/cookie-name";

/**
 * A presença do cookie só evita um ecrã privado vazio.
 * A validade do token é confirmada no servidor, com GET /auth/me.
 * O protocolo observado substitui o x-forwarded-proto enviado pelo cliente.
 */
export function middleware(request: NextRequest) {
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set(
    REQUEST_PROTO_HEADER,
    request.nextUrl.protocol === "https:" ? "https" : "http",
  );

  if (isPrivate(request.nextUrl.pathname) && !request.cookies.get(SESSION_COOKIE)?.value) {
    const login = request.nextUrl.clone();
    login.pathname = "/login";
    login.search = "";
    return NextResponse.redirect(login);
  }

  const response = NextResponse.next({
    request: { headers: requestHeaders },
  });
  if (isPrivate(request.nextUrl.pathname)) {
    response.headers.set("Cache-Control", "private, no-store");
  }
  return response;
}

function isPrivate(pathname: string): boolean {
  return pathname === "/inicio" || pathname === "/actores" || pathname.startsWith("/actores/");
}

export const config = {
  matcher: ["/inicio", "/login", "/actores", "/actores/:path*"],
};
