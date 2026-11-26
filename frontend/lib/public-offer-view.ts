/** Leitura e apresentação da descoberta pública.

O backend continua a ser a autoridade da pesquisa. Este módulo não
normaliza acentos nem espaços. Também não converte preços para número.
*/

export const PAGE_SIZE = 20;
export const HOME_LIMIT = 6;
export const MAX_OFFSET = 1000;
export const TEXT_LIMIT = 100;
export const NAVIGABLE_DEPTH = MAX_OFFSET + PAGE_SIZE;

export const PUBLIC_FIELD_NOTICE =
  "Esta informação poderá ser apresentada publicamente quando existir uma oferta publicada e elegível. Não introduza números de telefone, endereços de email ou outros dados pessoais nestes campos.";

export const PUBLIC_PUBLISH_NOTICE =
  "Ao publicar, a oferta e as informações públicas associadas poderão ser consultadas por qualquer visitante. Alterações posteriores aos campos públicos do actor, do produto ou da oferta podem reflectir-se nas ofertas elegíveis já publicadas. Publicar não é uma autorização de divulgação de contactos.";

export const INVALID_QUERY_MESSAGE =
  "Os parâmetros da pesquisa não são válidos. Corrija o endereço ou limpe os filtros.";

export const INVALID_OFFER_ADDRESS =
  "O endereço da oferta não é válido.";

export const OFFER_NOT_FOUND = "Oferta não encontrada.";

export const EMPTY_CATALOG = "Ainda não há ofertas publicadas.";
export const EMPTY_SEARCH = "Nenhuma oferta corresponde à pesquisa.";
export const STALE_PAGE =
  "Esta página já não tem ofertas. O catálogo pode ter mudado.";
export const LIMITED_RESULTS =
  "A pesquisa apresenta um conjunto limitado de resultados. Refine os filtros para chegar ao que procura.";

export const LOCATION_MISSING = "Localização não indicada";
export const COVERAGE_MISSING = "Área de actuação não indicada";
export const DELIVERY_MISSING = "Condições de entrega não indicadas";

export const AVAILABILITY_LABELS = {
  available: "Disponível",
  unavailable: "Indisponível",
} as const;

export const PRODUCER_KIND_LABELS = {
  person: "Pessoa",
  organization: "Organização",
} as const;

const ALLOWED_QUERY = ["q", "category", "location", "offset"] as const;
type FilterKey = "q" | "category" | "location";

const OFFER_ID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export type PublicAvailability = keyof typeof AVAILABILITY_LABELS;
export type ProducerKind = keyof typeof PRODUCER_KIND_LABELS;

export type PublicOffer = {
  id: string;
  price: string;
  currency: string;
  quantity: string;
  unit: string;
  availability: PublicAvailability;
  deliveryTerms: string | null;
  productName: string;
  productDescription: string;
  productCategory: string;
  productImage: string | null;
  producerName: string;
  producerKind: ProducerKind;
  producerLocation: string | null;
  producerCoverage: string | null;
};

export type PublicFilters = {
  q?: string;
  category?: string;
  location?: string;
  offset: number;
};

export type RawQuery = Record<string, string | string[] | undefined>;

export type QueryRead =
  | { kind: "ready"; filters: PublicFilters }
  | { kind: "invalid" };

export function isPublicOfferId(value: string): boolean {
  return OFFER_ID.test(value);
}

/** Só aceita q, category, location e offset. O resto invalida a leitura.

Um escalar repetido, um texto com mais de 100 caracteres ou um offset
fora de 0..1000 também invalidam. O valor rejeitado não é devolvido.
`limit` não faz parte do endereço da interface: a página tem 20 ofertas.
*/
export function readPublicQuery(raw: RawQuery): QueryRead {
  const filters: PublicFilters = { offset: 0 };
  for (const key of Object.keys(raw)) {
    if (!ALLOWED_QUERY.includes(key as (typeof ALLOWED_QUERY)[number])) {
      return { kind: "invalid" };
    }
    const value = raw[key];
    if (Array.isArray(value)) return { kind: "invalid" };
    if (value === undefined) continue;
    if (key === "offset") {
      const offset = canonicalOffset(value);
      if (offset === null) return { kind: "invalid" };
      filters.offset = offset;
      continue;
    }
    if (value.length > TEXT_LIMIT) return { kind: "invalid" };
    if (value !== "") filters[key as FilterKey] = value;
  }
  return { kind: "ready", filters };
}

export function listingHref(filters: PublicFilters): string {
  const params = new URLSearchParams();
  if (filters.q) params.set("q", filters.q);
  if (filters.category) params.set("category", filters.category);
  if (filters.location) params.set("location", filters.location);
  if (filters.offset > 0) params.set("offset", String(filters.offset));
  const query = params.toString();
  return query === "" ? "/ofertas" : `/ofertas?${query}`;
}

export function offerHref(id: string, filters: PublicFilters): string {
  if (!isPublicOfferId(id)) return "/ofertas";
  const list = listingHref(filters);
  const query = list.startsWith("/ofertas?") ? list.slice("/ofertas".length) : "";
  return `/ofertas/${id}${query}`;
}

/** Reconstrói o regresso só com os filtros permitidos. */
export function returnHref(raw: RawQuery): string {
  const read = readPublicQuery(raw);
  if (read.kind !== "ready") return "/ofertas";
  return listingHref(read.filters);
}

export function nextOffset(offset: number, shown: number, total: number): number | null {
  if (shown <= 0 || offset + shown >= total) return null;
  const next = offset + PAGE_SIZE;
  if (next > MAX_OFFSET) return null;
  return next;
}

export function previousOffset(offset: number): number | null {
  if (offset <= 0) return null;
  return offset > PAGE_SIZE ? offset - PAGE_SIZE : 0;
}

export function catalogIsLimited(total: number): boolean {
  return total > NAVIGABLE_DEPTH;
}

export function resultRange(offset: number, shown: number, total: number): string {
  const noun = total === 1 ? "1 oferta" : `${total} ofertas`;
  if (shown <= 0) return noun;
  return `${offset + 1}–${offset + shown} de ${noun}`;
}

export function shownText(value: string | null, fallback: string): string {
  if (value === null || value.trim() === "") return fallback;
  return value;
}

export function hasSearch(filters: PublicFilters): boolean {
  return Boolean(filters.q || filters.category || filters.location);
}

function canonicalOffset(value: string): number | null {
  if (!/^(0|[1-9][0-9]*)$/.test(value)) return null;
  let total = 0;
  for (const char of value) {
    total = total * 10 + (char.charCodeAt(0) - 48);
    if (total > MAX_OFFSET) return null;
  }
  return total;
}
