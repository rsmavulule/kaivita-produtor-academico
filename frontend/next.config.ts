import path from "path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Há um package-lock.json na pasta pessoal do utilizador. Sem esta raiz,
  // o Next.js sobe até lá e deixa de tratar frontend/ como o projecto.
  outputFileTracingRoot: path.resolve(process.cwd()),
};

export default nextConfig;
