import { existsSync, readFileSync } from "fs";
import path from "path";
import type { NextConfig } from "next";

loadHostApiUrl();

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Há um package-lock.json na pasta pessoal do utilizador. Sem esta raiz,
  // o Next.js sobe até lá e deixa de tratar frontend/ como o projecto.
  outputFileTracingRoot: path.resolve(process.cwd()),
  devIndicators: false,
  async headers() {
    return [
      {
        source: "/inicio",
        headers: [{ key: "Cache-Control", value: "private, no-store" }],
      },
      {
        source: "/login",
        headers: [{ key: "Cache-Control", value: "private, no-store" }],
      },
    ];
  },
};

/**
 * No `npm run dev`, API_URL vem do .env da raiz se o processo ainda não a tiver.
 * Só lê API_URL e, na falta dela, API_PORT. Não copia o segredo JWT.
 * No contentor a variável já vem do Compose e este ficheiro não existe.
 */
function loadHostApiUrl() {
  if (process.env.API_URL) return;
  const envPath = path.resolve(process.cwd(), "..", ".env");
  if (!existsSync(envPath)) return;
  let apiUrl = "";
  let apiPort = "";
  for (const line of readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const separator = trimmed.indexOf("=");
    if (separator === -1) continue;
    const key = trimmed.slice(0, separator).trim();
    const value = trimmed.slice(separator + 1).trim();
    if (key === "API_URL") apiUrl = value;
    if (key === "API_PORT") apiPort = value;
  }
  if (apiUrl) process.env.API_URL = apiUrl;
  else if (/^\d+$/.test(apiPort)) process.env.API_URL = `http://localhost:${apiPort}`;
}

export default nextConfig;
