"""Matriz de papéis e permissões do Nivelo, sincronizada com o banco a cada boot.

O código é a fonte da verdade: papéis e permissões que não estão aqui são removidos,
e usuários com papel desconhecido caem no papel de menor privilégio (`cliente`).

Na Fase 1 os papéis de negócio (`dono`, `encarregado`, `cliente`) ainda não têm
permissões granulares: a autorização deles chega na Fase 3, por vínculo com a empresa
e pela dependência `requer_papel`. Só o `admin` (da plataforma) tem permissões aqui.
"""
from sqlalchemy.orm import Session

from app.models.papel import Papel, role_permissions
from app.models.permissao import Permissao
from app.models.usuario import Usuario
from app.models.usuario_permissao import UsuarioPermissao

PAPEL_PADRAO = "cliente"

PERMISSOES_DEFINICAO = [
    {"action": "visualizar", "resource": "usuarios", "description": "Listar usuários cadastrados no sistema"},
    {"action": "gerenciar", "resource": "usuarios", "description": "Alterar dados e papéis de usuários"},
    {"action": "gerenciar", "resource": "papeis", "description": "Criar, alterar e listar papéis do sistema"},
    {"action": "gerenciar", "resource": "permissoes", "description": "Gerenciar matriz de permissões"},
    {"action": "visualizar", "resource": "logs", "description": "Consultar a trilha de auditoria do sistema"},
    {"action": "administrar", "resource": "sistema", "description": "Permissão exclusiva de administração da plataforma"},
]

PAPEIS_DEFINICAO = [
    {
        "name": "Dono",
        "slug": "dono",
        "description": "Dono da empresa: cria obras, convida a equipe e gerencia a assinatura",
        "permissoes": [],
    },
    {
        "name": "Encarregado",
        "slug": "encarregado",
        "description": "Registra e publica o diário nas obras em que é membro",
        "permissoes": [],
    },
    {
        "name": "Cliente",
        "slug": "cliente",
        "description": "Acompanha os diários publicados das obras em que é membro",
        "permissoes": [],
    },
    {
        "name": "Admin",
        "slug": "admin",
        "description": "Administrador da plataforma; não lê dados de obras",
        "permissoes": [f"{p['action']}:{p['resource']}" for p in PERMISSOES_DEFINICAO],
    },
]

LEGACY_ROLE_MAP = {
    "usuario": PAPEL_PADRAO,
    "admin": "admin",
}


def seed_rbac(db: Session) -> None:
    # 1. Cria as permissões da matriz
    perm_dict: dict[str, Permissao] = {}
    for p_data in PERMISSOES_DEFINICAO:
        perm = db.query(Permissao).filter(
            Permissao.action == p_data["action"],
            Permissao.resource == p_data["resource"],
        ).first()
        if not perm:
            perm = Permissao(action=p_data["action"], resource=p_data["resource"], description=p_data["description"])
            db.add(perm)
            db.flush()
        else:
            perm.description = p_data["description"]
        perm_dict[f"{perm.action}:{perm.resource}"] = perm

    # 2. Cria ou atualiza os papéis e associa as permissões
    roles_dict: dict[str, Papel] = {}
    for r_data in PAPEIS_DEFINICAO:
        role = db.query(Papel).filter(Papel.slug == r_data["slug"]).first()
        if not role:
            role = Papel(name=r_data["name"], slug=r_data["slug"], description=r_data["description"])
            db.add(role)
            db.flush()
        else:
            role.name = r_data["name"]
            role.description = r_data["description"]
        role.permissoes = [perm_dict[s] for s in r_data["permissoes"] if s in perm_dict]
        roles_dict[role.slug] = role
    db.flush()

    # 3. Usuários com papel fora da matriz caem no papel padrão
    for user in db.query(Usuario).all():
        target_slug = LEGACY_ROLE_MAP.get(user.role, user.role)
        if target_slug not in roles_dict:
            target_slug = PAPEL_PADRAO
        user.role = target_slug
        user.role_id = roles_dict[target_slug].id
    db.flush()

    # 4. Remove papéis e permissões que não estão mais na matriz (as associações saem antes,
    #    porque o SQLite dos testes não aplica ON DELETE CASCADE)
    for role in db.query(Papel).filter(Papel.slug.notin_(list(roles_dict))).all():
        db.execute(role_permissions.delete().where(role_permissions.c.role_id == role.id))
        db.delete(role)
    ids_validos = [p.id for p in perm_dict.values()]
    for perm in db.query(Permissao).filter(Permissao.id.notin_(ids_validos)).all():
        db.query(UsuarioPermissao).filter(UsuarioPermissao.permission_id == perm.id).delete()
        db.execute(role_permissions.delete().where(role_permissions.c.permission_id == perm.id))
        db.delete(perm)

    db.commit()
