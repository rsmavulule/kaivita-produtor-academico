import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

export function setAccess(input: {
  email: string;
  password: string;
  actorId: string;
  mode: "read" | "manage" | "revoke";
}): void {
  const backend = path.resolve(process.cwd(), "..", "backend");
  const venvPython = path.join(backend, ".venv", "Scripts", "python.exe");
  const python = existsSync(venvPython) ? venvPython : "python";
  const script = [
    "import json, sys, uuid",
    "from sqlalchemy import select",
    "from sqlalchemy.orm import Session",
    "from app.accounts import create_active_user",
    "from app.db import engine",
    "from app.identity import AccessLevel, AccessStatus, User, UserActorAccess",
    "payload = json.loads(sys.stdin.read())",
    "email = payload['email'].strip().lower()",
    "actor_id = uuid.UUID(payload['actorId'])",
    "mode = payload['mode']",
    "with Session(engine) as session:",
    "    user = session.scalar(select(User).where(User.email == email))",
    "    if user is None:",
    "        user = create_active_user(session, email, payload['password'])",
    "    access = session.get(UserActorAccess, (user.id, actor_id))",
    "    if mode == 'revoke':",
    "        access.status = AccessStatus.REVOKED",
    "    else:",
    "        level = AccessLevel.READ if mode == 'read' else AccessLevel.MANAGE",
    "        if access is None:",
    "            session.add(UserActorAccess(user_id=user.id, actor_id=actor_id, access_level=level, status=AccessStatus.ACTIVE))",
    "        else:",
    "            access.access_level = level",
    "            access.status = AccessStatus.ACTIVE",
    "    session.commit()",
  ].join("\n");
  const result = spawnSync(python, ["-c", script], {
    cwd: backend,
    input: JSON.stringify(input),
    encoding: "utf8",
  });
  if (result.status !== 0) {
    const detail = `${result.stderr ?? ""}\n${result.stdout ?? ""}`.replaceAll(input.password, "[omisso]");
    throw new Error(`Não foi possível preparar a representação de teste. ${detail.trim()}`);
  }
}
