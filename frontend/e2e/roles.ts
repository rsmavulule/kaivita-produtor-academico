import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

export function setCommercialRoles(input: { actorId: string; roles: string[] }): void {
  const backend = path.resolve(process.cwd(), "..", "backend");
  const venvPython = path.join(backend, ".venv", "Scripts", "python.exe");
  const python = existsSync(venvPython) ? venvPython : "python";
  const script = [
    "import json, sys, uuid",
    "from sqlalchemy.orm import Session",
    "from app.actor_roles import replace_actor_roles",
    "from app.db import engine",
    "from app.identity import Actor, RoleCode",
    "payload = json.loads(sys.stdin.read())",
    "actor_id = uuid.UUID(payload['actorId'])",
    "codes = [RoleCode(code) for code in payload['roles']]",
    "with Session(engine) as session:",
    "    actor = session.get(Actor, actor_id)",
    "    replace_actor_roles(session, actor, codes)",
    "    session.commit()",
  ].join("\n");
  const result = spawnSync(python, ["-c", script], {
    cwd: backend,
    input: JSON.stringify(input),
    encoding: "utf8",
  });
  if (result.status !== 0) {
    throw new Error("Não foi possível preparar os papéis de teste.");
  }
}
