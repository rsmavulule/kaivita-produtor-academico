import { cookies, headers } from "next/headers";

import { SESSION_COOKIE } from "./cookie-name";
import { REQUEST_PROTO_HEADER, secureCookieFromObserved, sessionCookieOptions } from "./cookie-policy";

export async function readSessionToken(): Promise<string | null> {
  const jar = await cookies();
  const value = jar.get(SESSION_COOKIE)?.value;
  if (!value) return null;
  return value;
}

export async function writeSession(token: string, maxAge: number): Promise<void> {
  const jar = await cookies();
  jar.set(SESSION_COOKIE, token, await cookieOptions(maxAge));
}

export async function clearSession(): Promise<void> {
  const jar = await cookies();
  jar.set(SESSION_COOKIE, "", await cookieOptions(0));
}

async function cookieOptions(maxAge: number) {
  const headerList = await headers();
  return sessionCookieOptions({
    secure: secureCookieFromObserved(headerList.get(REQUEST_PROTO_HEADER)),
    maxAge,
  });
}
