export const CONNECTION_MESSAGE =
  "Não foi possível contactar o serviço. Tente novamente.";
export const CREDENTIALS_MESSAGE = "Credenciais inválidas.";
export const REJECTED_MESSAGE = "Pedido recusado.";

export type ApiKind = "unauthorized" | "validation" | "unavailable" | "rejected";

export type ParsedApiError = {
  kind: ApiKind;
  status: number;
  message: string;
  emailError?: string;
  passwordError?: string;
};

/** 401 é só autenticação. Rede e 5xx não terminam a sessão. */
export function kindForStatus(status: number): ApiKind {
  if (status === 401) return "unauthorized";
  if (status === 422) return "validation";
  if (status === 0 || status >= 500) return "unavailable";
  return "rejected";
}

export function parseApiError(status: number, body: unknown): ParsedApiError {
  const kind = kindForStatus(status);
  if (kind === "unauthorized") {
    return { kind, status, message: "Acesso recusado." };
  }
  if (kind === "unavailable") {
    return { kind, status, message: CONNECTION_MESSAGE };
  }
  if (kind === "validation") {
    return validationError(status, body);
  }
  return { kind, status, message: REJECTED_MESSAGE };
}

function validationError(status: number, body: unknown): ParsedApiError {
  const issues = validationIssues(body);
  let emailError: string | undefined;
  let passwordError: string | undefined;
  for (const issue of issues) {
    const text = cleanMessage(issue.msg);
    if (issue.loc.includes("email")) emailError = text;
    else if (issue.loc.includes("password")) passwordError = text;
  }
  const detail = stringDetail(body);
  const message =
    emailError || passwordError
      ? "Alguns campos não foram aceites."
      : (detail ?? "Alguns campos não foram aceites.");
  return { kind: "validation", status, message, emailError, passwordError };
}

function validationIssues(body: unknown): { loc: unknown[]; msg: string }[] {
  if (!body || typeof body !== "object" || !("detail" in body)) return [];
  const detail = (body as { detail: unknown }).detail;
  if (!Array.isArray(detail)) return [];
  return detail.flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const record = item as { loc?: unknown; msg?: unknown };
    const loc = Array.isArray(record.loc) ? record.loc : [];
    const msg = typeof record.msg === "string" ? record.msg : "";
    if (msg === "") return [];
    return [{ loc, msg }];
  });
}

function stringDetail(body: unknown): string | null {
  if (!body || typeof body !== "object" || !("detail" in body)) return null;
  const detail = (body as { detail: unknown }).detail;
  if (typeof detail !== "string") return null;
  return cleanMessage(detail);
}

function cleanMessage(message: string): string {
  const withoutPrefix = message.startsWith("Value error, ")
    ? message.slice("Value error, ".length)
    : message;
  if (withoutPrefix.length === 0 || withoutPrefix.length > 180) {
    return "Valor inválido.";
  }
  if (withoutPrefix.includes("eyJ")) return "Valor inválido.";
  return withoutPrefix;
}
