import { CONNECTION_MESSAGE } from "../../../../../../lib/errors";
import { readPublicContacts } from "../../../../../../lib/public-contacts";

export const dynamic = "force-dynamic";

const headers = { "cache-control": "no-store" };

export async function GET(
  _request: Request,
  context: { params: Promise<{ offerId: string }> },
) {
  const { offerId } = await context.params;
  const result = await readPublicContacts(offerId);
  if (result.kind === "invalid") {
    return Response.json({ detail: "Endereço inválido." }, { status: 422, headers });
  }
  if (result.kind === "missing") {
    return Response.json({ detail: "Oferta não encontrada." }, { status: 404, headers });
  }
  if (result.kind === "ready") {
    return Response.json({ items: result.items }, { headers });
  }
  return Response.json({ detail: CONNECTION_MESSAGE }, { status: 503, headers });
}
