import { cache } from "react";

import { requestMe } from "./api";
import { readSessionToken } from "./session";

export type SessionView =
  | { kind: "anonymous" }
  | { kind: "invalid" }
  | { kind: "unavailable" }
  | { kind: "ready"; email: string };

/** Uma leitura de /auth/me por pedido, partilhada pelo layout e pela página. */
export const loadSession = cache(async (): Promise<SessionView> => {
  const token = await readSessionToken();
  if (!token) return { kind: "anonymous" };
  return requestMe(token);
});
