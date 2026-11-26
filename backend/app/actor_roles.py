"""Associação dos papéis comerciais a um actor.

O catálogo ``roles`` já foi semeado no I1.1. Estas funções não inserem,
não alteram e não apagam linhas dessa tabela. Também não mudam
``user_actor_access`` de ninguém, excepto o acesso ``manage`` criado
para o utilizador autenticado no momento em que o actor nasce.

A lista vazia é recusada aqui. A base continua a permitir um actor sem
papéis: a obrigatoriedade é desta API, não um CHECK do I1.1.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.identity import (
    AccessLevel,
    AccessStatus,
    Actor,
    ActorKind,
    ActorRole,
    ActorStatus,
    Role,
    RoleCode,
    User,
    UserActorAccess,
)

CATALOG_ORDER = (RoleCode.PRODUCER, RoleCode.BUYER, RoleCode.PARTNER)


def parse_role_codes(value: object) -> list[RoleCode]:
    """Converte a lista pedida nos três códigos fechados.

    Código desconhecido, repetição e lista vazia falham antes de
    qualquer escrita. A ordem devolvida é a do pedido; a resposta
    da API volta a ordenar pelo catálogo.
    """

    if not isinstance(value, list):
        raise ValueError("Papéis inválidos.")

    codes: list[RoleCode] = []
    seen: set[RoleCode] = set()
    for item in value:
        if isinstance(item, RoleCode):
            code = item
        elif isinstance(item, str):
            try:
                code = RoleCode(item)
            except ValueError:
                raise ValueError("Papel desconhecido.") from None
        else:
            raise ValueError("Papel desconhecido.")
        if code in seen:
            raise ValueError("Papel repetido.")
        seen.add(code)
        codes.append(code)

    if not codes:
        raise ValueError("É necessário pelo menos um papel.")
    return codes


def resolve_roles(session: Session, codes: list[RoleCode]) -> list[Role]:
    """Lê as linhas já existentes. Não cria um papel em falta."""

    checked = parse_role_codes(codes)
    found = session.scalars(select(Role).where(Role.code.in_(checked))).all()
    by_code = {RoleCode(role.code): role for role in found}
    if set(by_code) != set(checked):
        raise RuntimeError("Catálogo de papéis incompleto.")
    return _ordered(by_code[code] for code in CATALOG_ORDER if code in by_code)


def catalog(session: Session) -> list[Role]:
    """Os papéis globais, na ordem producer, buyer, partner."""

    return _ordered(session.scalars(select(Role)).all())


def roles_of(session: Session, actor: Actor) -> list[Role]:
    rows = session.scalars(
        select(Role)
        .join(ActorRole, ActorRole.role_id == Role.id)
        .where(ActorRole.actor_id == actor.id)
    ).all()
    return _ordered(rows)


def create_represented_actor(
    session: Session,
    user: User,
    kind: ActorKind,
    display_name: str,
    general_location: str | None,
    codes: list[RoleCode],
    coverage_area: str | None = None,
) -> tuple[Actor, list[Role]]:
    """Cria o actor, os papéis e o acesso do criador na mesma transacção.

    O savepoint desfaz as três escritas se a última falhar. Quem confirma
    o pedido é a sessão de ``get_session``, uma única vez, no fim.
    """

    selected = resolve_roles(session, codes)
    with session.begin_nested():
        actor = Actor(
            kind=kind,
            display_name=display_name,
            general_location=general_location,
            coverage_area=coverage_area,
            status=ActorStatus.ACTIVE,
        )
        session.add(actor)
        session.flush()
        for role in selected:
            session.add(ActorRole(actor_id=actor.id, role_id=role.id))
        grant_creator(session, user, actor)
        session.flush()
    return actor, selected


def grant_creator(session: Session, user: User, actor: Actor) -> None:
    """O criador fica com ``manage`` activo. O pedido não escolhe o nível."""

    session.add(
        UserActorAccess(
            user_id=user.id,
            actor_id=actor.id,
            access_level=AccessLevel.MANAGE,
            status=AccessStatus.ACTIVE,
        )
    )


def replace_actor_roles(
    session: Session,
    actor: Actor,
    codes: list[RoleCode],
) -> list[Role]:
    """Substitui o conjunto de papéis do actor.

    A mesma lista, noutra ordem, não escreve. Uma falha a meio repõe
    o conjunto anterior. ``roles`` e ``user_actor_access`` não são tocados.
    """

    selected = resolve_roles(session, codes)
    current_links = list(
        session.scalars(select(ActorRole).where(ActorRole.actor_id == actor.id))
    )
    current_ids = {link.role_id for link in current_links}
    desired_ids = {role.id for role in selected}
    if current_ids == desired_ids:
        return selected

    with session.begin_nested():
        apply_role_replacement(session, actor, current_links, selected)
        session.flush()
    return selected


def apply_role_replacement(
    session: Session,
    actor: Actor,
    current_links: list[ActorRole],
    selected: list[Role],
) -> None:
    desired = {role.id for role in selected}
    present = {link.role_id for link in current_links}
    for link in current_links:
        if link.role_id not in desired:
            session.delete(link)
    for role in selected:
        if role.id not in present:
            session.add(ActorRole(actor_id=actor.id, role_id=role.id))


def _ordered(roles) -> list[Role]:
    rank = {code: index for index, code in enumerate(CATALOG_ORDER)}
    return sorted(roles, key=lambda role: rank[RoleCode(role.code)])
