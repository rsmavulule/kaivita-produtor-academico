import { NextResponse, type NextRequest } from "next/server";

import { requestMe } from "../../../lib/api";
import { SESSION_COOKIE } from "../../../lib/cookie-name";
import { secureCookieFromObserved, sessionCookieOptions } from "../../../lib/cookie-policy";

/**
 * Só apaga o cookie quando a API recusa o token com 401.
 * Uma falha de rede ou um 5xx devolve o utilizador a /inicio, com o cookie intacto.
 */
export async function GET(request: NextRequest) {
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (!token) return redirectTo("/login");

  const session = await requestMe(token);
  if (session.kind !== "invalid") return redirectTo("/inicio");

  const response = redirectTo("/login", "sessao");
  const secure = secureCookieFromObserved(request.nextUrl.protocol);
  response.cookies.set(SESSION_COOKIE, "", sessionCookieOptions({ secure, maxAge: 0 }));
  return response;
}

/**
 * Caminho relativo de propósito. No contentor, request.nextUrl usa o endereço
 * interno (0.0.0.0:3000). Um Location absoluto mandaria o browser para lá.
 * O caminho é fixo: não há redireccionamento para um host escolhido pelo pedido.
 */
function redirectTo(pathname: "/login" | "/inicio", motivo?: "sessao") {
  const location = motivo ? `${pathname}?motivo=${motivo}` : pathname;
  return new NextResponse(null, {
    status: 307,
    headers: { location },
  });
}
