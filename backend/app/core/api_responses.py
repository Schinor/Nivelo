"""Exemplos de respostas de erro para o Swagger (OpenAPI).

FastAPI só documenta automaticamente o código de sucesso e o 422 de validação.
Os dicionários aqui cobrem os códigos de erro que as rotas realmente podem
devolver, com um payload de exemplo real (mesmo `detail` usado no código).
"""

UNAUTHORIZED = {
    401: {
        "description": "Não autenticado (token ausente ou inválido)",
        "content": {
            "application/json": {
                "examples": {
                    "sem_token": {"value": {"detail": "Token não enviado"}},
                    "token_invalido": {"value": {"detail": "Token inválido ou expirado"}},
                }
            }
        },
    }
}


def forbidden(permission: str) -> dict:
    return {
        403: {
            "description": "Autenticado, mas sem a permissão necessária (evento 'acesso_negado' é registrado na auditoria)",
            "content": {
                "application/json": {"example": {"detail": f"Acesso negado: permissão '{permission}' necessária"}}
            },
        }
    }


AUTH_SERVICE_INDISPONIVEL = {
    503: {
        "description": "auth-service inacessível",
        "content": {"application/json": {"example": {"detail": "Serviço de autenticação inacessível: ..."}}},
    }
}

LOG_SERVICE_INDISPONIVEL = {
    503: {
        "description": "log-service inacessível",
        "content": {"application/json": {"example": {"detail": "Serviço de auditoria indisponível"}}},
    }
}

CREDENCIAIS_INVALIDAS = {
    401: {
        "description": "E-mail ou senha incorretos",
        "content": {"application/json": {"example": {"detail": "E-mail ou senha incorretos"}}},
    }
}

EMAIL_JA_CADASTRADO = {
    400: {
        "description": "E-mail já cadastrado",
        "content": {"application/json": {"example": {"detail": "E-mail já cadastrado"}}},
    }
}

NOT_FOUND_USER = {
    404: {
        "description": "Usuário não encontrado",
        "content": {"application/json": {"example": {"detail": "Usuário não encontrado"}}},
    }
}


def gestao_usuario_invalida(**exemplos: str) -> dict:
    """400 das rotas de gestão de usuários: ação sobre a própria conta, mais os exemplos da rota."""
    todos = {"propria_conta": "Você não pode alterar ou remover a sua própria conta por aqui", **exemplos}
    return {
        400: {
            "description": "Ação sobre a própria conta ou dados inválidos",
            "content": {
                "application/json": {
                    "examples": {nome: {"value": {"detail": detail}} for nome, detail in todos.items()}
                }
            },
        }
    }


RESET_TOKEN_INVALIDO = {
    400: {
        "description": "Token de redefinição inválido, expirado, já usado ou senha fraca",
        "content": {
            "application/json": {
                "examples": {
                    "inexistente": {"value": {"detail": "Token de recuperação inválido ou inexistente."}},
                    "senha_curta": {"value": {"detail": "A nova senha deve ter no mínimo 6 caracteres."}},
                }
            }
        },
    }
}

STRIPE_NAO_CONFIGURADO = {
    503: {
        "description": "Stripe não configurado neste ambiente (STRIPE_* ausentes) ou auth-service inacessível",
        "content": {"application/json": {"example": {"detail": "Pagamentos não configurados neste ambiente"}}},
    }
}
