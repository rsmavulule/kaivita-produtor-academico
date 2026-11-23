import { headers } from "next/headers";

/** O pedido que muda a sessão tem de nascer nesta origem. O destino é fixo. */
export async function sameOrigin(): Promise<boolean> {
  const headerList = await headers();
  return originAllowed({
    origin: headerList.get("origin"),
    host: headerList.get("host"),
    fetchSite: headerList.get("sec-fetch-site"),
  });
}

/**
 * Origin ausente ou de outro host recusa o pedido. O proxy de confiança
 * reencaminha o Host público; este código não aceita X-Forwarded-Host,
 * senão uma origem forjada passaria a coincidir.
 */
export function originAllowed(input: {
  origin: string | null;
  host: string | null;
  fetchSite: string | null;
}): boolean {
  if (!input.origin || !input.host) return false;

  let originUrl: URL;
  try {
    originUrl = new URL(input.origin);
  } catch {
    return false;
  }
  if (originUrl.username || originUrl.password) return false;

  let hostUrl: URL;
  try {
    hostUrl = new URL(`${originUrl.protocol}//${input.host.trim()}`);
  } catch {
    return false;
  }
  if (hostUrl.host.toLowerCase() !== originUrl.host.toLowerCase()) return false;

  if (input.fetchSite && input.fetchSite !== "same-origin") return false;
  return true;
}
