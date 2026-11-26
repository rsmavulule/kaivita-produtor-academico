"use client";

import { useEffect, useRef, useState } from "react";

import { CHANNEL_LABELS, EMPTY_PUBLIC_CONTACTS, PUBLIC_OFFER_UNAVAILABLE } from "../lib/contact-view";
import { CONNECTION_MESSAGE } from "../lib/errors";

type ShownContact = { channel: "phone" | "email" | "whatsapp"; value: string };

type Phase = "idle" | "loading" | "ready" | "empty" | "missing" | "failed";

/**
 * Os contactos só entram depois do clique. Uma resposta atrasada de outra
 * oferta ou de uma consulta já substituída é ignorada. A página aberta
 * conserva o último resultado até nova consulta, ocultação ou navegação.
 */
export function PublicContacts({ offerId }: { offerId: string }) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [items, setItems] = useState<ShownContact[]>([]);
  const [copied, setCopied] = useState<string | null>(null);
  const generation = useRef(0);

  useEffect(() => {
    generation.current += 1;
    setPhase("idle");
    setItems([]);
    setCopied(null);
  }, [offerId]);

  async function consult() {
    const request = ++generation.current;
    const requestedOffer = offerId;
    setPhase("loading");
    setItems([]);
    setCopied(null);
    try {
      const response = await fetch(`/api/public/ofertas/${requestedOffer}/contactos`, {
        method: "GET",
        headers: { accept: "application/json" },
        cache: "no-store",
      });
      if (request !== generation.current || requestedOffer !== offerId) return;
      if (response.status === 404) {
        setPhase("missing");
        return;
      }
      if (!response.ok) {
        setPhase("failed");
        return;
      }
      const body = (await response.json()) as { items?: unknown };
      if (request !== generation.current || requestedOffer !== offerId) return;
      const parsed = parseShown(body.items);
      if (parsed === null) {
        setPhase("failed");
        return;
      }
      setItems(parsed);
      setPhase(parsed.length === 0 ? "empty" : "ready");
    } catch {
      if (request !== generation.current) return;
      setItems([]);
      setPhase("failed");
    }
  }

  function hide() {
    generation.current += 1;
    setItems([]);
    setCopied(null);
    setPhase("idle");
  }

  return (
    <section className="form" aria-busy={phase === "loading"}>
      <h2>Contactos comerciais</h2>
      <p className="note">A consulta é feita quando a pedir. A negociação ocorre fora da plataforma.</p>
      <p className="links">
        <button className="primary" type="button" onClick={consult} disabled={phase === "loading"}>
          {phase === "loading" ? "A consultar…" : "Ver contactos"}
        </button>
        {phase !== "idle" ? (
          <button className="secondary" type="button" onClick={hide}>
            Ocultar contactos
          </button>
        ) : null}
      </p>
      {phase === "empty" ? <p className="note">{EMPTY_PUBLIC_CONTACTS}</p> : null}
      {phase === "missing" ? <p className="alert" role="alert">{PUBLIC_OFFER_UNAVAILABLE}</p> : null}
      {phase === "failed" ? <p className="alert" role="alert">{CONNECTION_MESSAGE}</p> : null}
      {phase === "ready" ? (
        <ul className="actor-list">
          {items.map((item) => {
            const link = safeLink(item.channel, item.value);
            return (
              <li key={`${item.channel}:${item.value}`}>
                <p>{CHANNEL_LABELS[item.channel]}</p>
                <p className="contact-value">{item.value}</p>
                <p className="links">
                  <button className="secondary" type="button" onClick={() => copyValue(item.value, setCopied)}>
                    {copied === item.value ? "Copiado" : "Copiar contacto"}
                  </button>
                  {link ? <a href={link.href}>{link.label}</a> : null}
                </p>
              </li>
            );
          })}
        </ul>
      ) : null}
    </section>
  );
}

function parseShown(value: unknown): ShownContact[] | null {
  if (!Array.isArray(value)) return null;
  const items: ShownContact[] = [];
  for (const item of value) {
    if (!item || typeof item !== "object") return null;
    const record = item as Record<string, unknown>;
    if (Object.keys(record).some((key) => key !== "channel" && key !== "value")) return null;
    if (record.channel !== "phone" && record.channel !== "email" && record.channel !== "whatsapp") return null;
    if (typeof record.value !== "string" || record.value.trim() === "") return null;
    items.push({ channel: record.channel, value: record.value });
  }
  return items;
}

function safeLink(
  channel: ShownContact["channel"],
  value: string,
): { href: string; label: string } | null {
  if (channel === "email" && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) && !/[:/?#]/.test(value)) {
    return { href: `mailto:${value}`, label: "Abrir o correio" };
  }
  if ((channel === "phone" || channel === "whatsapp") && /^\+[1-9][0-9]{7,14}$/.test(value)) {
    if (channel === "phone") return { href: `tel:${value}`, label: "Ligar" };
    return { href: `https://wa.me/${value.slice(1)}`, label: "Abrir o WhatsApp" };
  }
  return null;
}

async function copyValue(value: string, setCopied: (value: string | null) => void) {
  try {
    await navigator.clipboard.writeText(value);
    setCopied(value);
  } catch {
    setCopied(null);
  }
}
