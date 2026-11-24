const DECIMAL_TEXT = /^\d+(\.\d+)?$/;

export type DecimalInput =
  | { kind: "empty" }
  | { kind: "value"; text: string }
  | { kind: "invalid" };

/** Lê um decimal escrito pelo utilizador, sem ponto flutuante.

Uma vírgula isolada passa a ponto. Ponto e vírgula juntos, ou mais de um
separador, ficam inválidos: não há leitura de milhares.
*/
export function readDecimal(raw: string): DecimalInput {
  if (raw === "") return { kind: "empty" };
  const trimmed = raw.trim();
  if (trimmed === "") return { kind: "invalid" };
  const commas = count(trimmed, ",");
  const dots = count(trimmed, ".");
  if ((commas > 0 && dots > 0) || commas > 1 || dots > 1) return { kind: "invalid" };
  const text = trimmed.replace(",", ".");
  if (!DECIMAL_TEXT.test(text)) return { kind: "invalid" };
  return { kind: "value", text };
}

export function decimalForApi(raw: string): string | null {
  const read = readDecimal(raw);
  if (read.kind === "empty") return null;
  if (read.kind === "value") return read.text;
  return raw;
}

function count(value: string, mark: string): number {
  let total = 0;
  for (const char of value) if (char === mark) total += 1;
  return total;
}
