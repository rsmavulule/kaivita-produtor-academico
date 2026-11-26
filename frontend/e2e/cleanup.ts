import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

import { manifestEmails } from "./manifest";

export function cleanupRunAccounts(): void {
  const emails = manifestEmails();
  if (emails.length === 0) return;
  const backend = path.resolve(process.cwd(), "..", "backend");
  const venvPython = path.join(backend, ".venv", "Scripts", "python.exe");
  const python = existsSync(venvPython) ? venvPython : "python";
  const script = [
    "import json, sys",
    "from sqlalchemy import delete, or_, select",
    "from sqlalchemy.orm import Session",
    "from app.db import engine",
    "from app.identity import Actor, ActorRole, User, UserActorAccess",
    "from app.contacts import PublicContact",
    "from app.offers import Offer, OfferStatusEvent",
    "from app.products import Product",
    "from app.publication import PublicationAuthorization",
    "emails = json.loads(sys.stdin.read())",
    "with Session(engine) as session:",
    "    users = list(session.scalars(select(User).where(User.email.in_(emails))))",
    "    user_ids = [user.id for user in users]",
    "    if user_ids:",
    "        accesses = list(session.scalars(select(UserActorAccess).where(UserActorAccess.user_id.in_(user_ids))))",
    "        actor_ids = {access.actor_id for access in accesses}",
    "        for actor_id in actor_ids:",
    "            others = session.scalar(select(UserActorAccess.user_id).where(UserActorAccess.actor_id == actor_id, UserActorAccess.user_id.not_in(user_ids)))",
    "            if others is not None:",
    "                continue",
    "            session.execute(delete(OfferStatusEvent).where(OfferStatusEvent.offer_id.in_(select(Offer.id).where(Offer.owner_actor_id == actor_id))))",
    "            session.execute(delete(PublicationAuthorization).where(PublicationAuthorization.actor_id == actor_id))",
    "            session.execute(delete(PublicContact).where(PublicContact.actor_id == actor_id))",
    "            session.execute(delete(Offer).where(Offer.owner_actor_id == actor_id))",
    "            session.execute(delete(Product).where(Product.owner_actor_id == actor_id))",
    "            session.execute(delete(ActorRole).where(ActorRole.actor_id == actor_id))",
    "            session.execute(delete(UserActorAccess).where(UserActorAccess.actor_id == actor_id))",
    "            actor = session.get(Actor, actor_id)",
    "            if actor is not None:",
    "                session.delete(actor)",
    "        session.execute(delete(UserActorAccess).where(UserActorAccess.user_id.in_(user_ids)))",
    "        remaining = session.scalar(select(PublicationAuthorization.id).where(or_(PublicationAuthorization.granted_by_user_id.in_(user_ids), PublicationAuthorization.revoked_by_user_id.in_(user_ids))))",
    "        if remaining is not None:",
    "            raise RuntimeError('autorização fora dos actores desta execução')",
    "        remaining_event = session.scalar(select(OfferStatusEvent.id).where(OfferStatusEvent.performed_by_user_id.in_(user_ids)))",
    "        if remaining_event is not None:",
    "            raise RuntimeError('evento de oferta fora dos actores desta execução')",
    "        for user in users:",
    "            session.delete(user)",
    "        session.commit()",
    "print(len(users))",
  ].join("\n");
  const result = spawnSync(python, ["-c", script], {
    cwd: backend,
    input: JSON.stringify(emails),
    encoding: "utf8",
  });
  if (result.status !== 0) {
    throw new Error("A limpeza dos dados desta execução não concluiu.");
  }
}
