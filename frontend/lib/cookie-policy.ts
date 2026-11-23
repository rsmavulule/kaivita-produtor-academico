/**
 * Atributos do cookie de sessão.
 * Secure segue o protocolo que o Next.js observou na ligação, gravado pelo
 * middleware. Não segue o x-forwarded-proto cru: um cliente pode enviá-lo
 * com o valor http e o Next.js conserva esse valor mesmo em TLS.
 * Em HTTP local e no Compose o protocolo observado é http e Secure fica
 * desligado. Em HTTPS directo fica ligado. Um proxy que termina TLS e
 * envia x-forwarded-proto: https faz o Next.js observar https.
 */
export const REQUEST_PROTO_HEADER = "x-kaivita-proto";

export function requestIsHttps(input: {
  protocol?: string | null;
  forwardedProto?: string | null;
}): boolean {
  const protocol = normalizeProto(input.protocol);
  if (protocol === "https") return true;
  if (protocol === "http") return false;
  return splitProto(input.forwardedProto).includes("https");
}

/** Só um http observado desliga Secure. Valor em falta fica ligado. */
export function secureCookieFromObserved(protocol: string | null | undefined): boolean {
  return normalizeProto(protocol) !== "http";
}

export function sessionCookieOptions(input: { secure: boolean; maxAge: number }) {
  return {
    httpOnly: true as const,
    sameSite: "lax" as const,
    secure: input.secure,
    path: "/",
    maxAge: input.maxAge,
  };
}

function normalizeProto(value: string | null | undefined): "https" | "http" | null {
  if (!value) return null;
  const token = value.trim().toLowerCase().replace(/:$/, "");
  if (token === "https" || token === "http") return token;
  return null;
}

function splitProto(value: string | null | undefined): string[] {
  if (!value) return [];
  return value
    .split(",")
    .map((part) => part.trim().toLowerCase())
    .filter((part) => part === "http" || part === "https");
}
