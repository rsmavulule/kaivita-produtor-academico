export const CONTACT_NOT_FOUND = "Contacto não encontrado.";
export const AUTHORIZATION_NOT_FOUND = "Autorização não encontrada.";
export const DUPLICATE_CONTACT = "Já existe um contacto activo com este canal e valor.";
export const INACTIVE_CONTACT = "O contacto inactivo não pode ser alterado.";
export const STALE_REVISION =
  "A revisão do contacto está desactualizada. Consulte o contacto novamente.";
export const NOTICE_VERSION = "v1";
export const NOTICE_V1 =
  "O representante confirma a divulgação do contacto comercial agora apresentado, no canal indicado. A finalidade é a descoberta comercial de ofertas. Qualquer visitante poderá consultar esse contacto. Terceiros poderão copiá-lo. A revogação impede consultas posteriores nesta plataforma, mas não apaga cópias já feitas por terceiros. O representante declara ter autorização adequada para divulgar o contacto. Esta confirmação operacional não prova, por si, o consentimento pessoal do titular nem a conformidade jurídica integral.";

export const CHANNELS = ["phone", "email", "whatsapp"] as const;
export type ContactChannel = (typeof CHANNELS)[number];
export type ContactStatus = "active" | "inactive";
export type ContactVisibility = "private" | "public";
export type AuthorizationStatus = "granted" | "revoked";
export type RevocationReason = "manual" | "contact_changed" | "contact_deactivated";

export const CHANNEL_LABELS: Record<ContactChannel, string> = {
  phone: "Telefone",
  email: "Email",
  whatsapp: "WhatsApp",
};
export const STATUS_LABELS: Record<ContactStatus, string> = {
  active: "Activo",
  inactive: "Inactivo",
};
export const VISIBILITY_LABELS: Record<ContactVisibility, string> = {
  private: "Privado",
  public: "Visibilidade pública",
};
export const AUTHORIZATION_LABELS: Record<AuthorizationStatus, string> = {
  granted: "Vigente",
  revoked: "Revogada",
};
export const REASON_LABELS: Record<RevocationReason, string> = {
  manual: "Revogação manual",
  contact_changed: "Alteração do contacto",
  contact_deactivated: "Desactivação do contacto",
};

export const PURPOSE_LABEL = "Descoberta comercial de ofertas";
export const REGISTER_NOTICE =
  "Registar o contacto não autoriza a sua divulgação. A divulgação exige uma confirmação própria.";
export const CHANGE_NOTICE =
  "Uma alteração efectiva do canal ou do valor revoga a autorização vigente e exige nova autorização. Uma alteração equivalente, depois da normalização, preserva a autorização existente.";
export const DEACTIVATE_NOTICE =
  "A desactivação revoga a autorização vigente, quando existir. O contacto não é apagado e não volta a activo.";
export const REVOKE_NOTICE =
  "A revogação impede novas consultas públicas que observem o estado confirmado. Não apaga informação que terceiros já tenham copiado ou guardado.";
export const PUBLIC_GAP_NOTICE =
  "Uma autorização vigente não torna o contacto consultável se não existir uma oferta elegível.";
export const EMPTY_PUBLIC_CONTACTS =
  "Não existem contactos comerciais disponíveis para esta oferta.";
export const PUBLIC_OFFER_UNAVAILABLE = "Oferta não encontrada ou indisponível.";

export type ContactView = {
  id: string;
  channel: ContactChannel;
  value: string;
  visibility: ContactVisibility;
  status: ContactStatus;
  revision: number;
};

export type AuthorizationView = {
  id: string;
  contactId: string;
  contactRevision: number;
  channel: ContactChannel;
  noticeVersion: string;
  status: AuthorizationStatus;
  grantedAt: string;
  revokedAt: string | null;
  reason: RevocationReason | null;
};

export function isChannel(value: unknown): value is ContactChannel {
  return value === "phone" || value === "email" || value === "whatsapp";
}

export function currentAuthorization(
  items: AuthorizationView[],
): AuthorizationView | null {
  return items.find((item) => item.status === "granted") ?? null;
}

export function formatWhen(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Data indisponível";
  return new Intl.DateTimeFormat("pt-PT", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "Africa/Maputo",
  }).format(date);
}
