import html
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger("auth-service.email")


class EmailNotConfiguredError(RuntimeError):
    """Credenciais SMTP ausentes: o e-mail não pode ser enviado."""


def send_password_reset_email(to_email: str, token: str, user_name: str = "Usuário") -> bool:
    """
    Envia e-mail real com link de redefinição de senha via SMTP (Mailtrap).
    O link aponta sempre para a rota pública da API (porta pública),
    garantindo que o auth-service permaneça isolado na rede interna Docker.
    """
    catalogo_url = (settings.CATALOGO_URL or "http://localhost:8000").strip(" \"'").rstrip("/")
    reset_url = f"{catalogo_url}/reset-password?token={token}"
    safe_name = html.escape(user_name)
    subject = "Redefinição de senha — Nivelo"

    smtp_host = (settings.MAILTRAP_HOST or "sandbox.smtp.mailtrap.io").strip(" \"'")
    try:
        smtp_port = int(str(settings.MAILTRAP_PORT).strip(" \"'"))
    except Exception:
        smtp_port = 2525

    smtp_user = (settings.MAILTRAP_USERNAME or "").strip(" \"'")
    smtp_pass = (settings.MAILTRAP_PASSWORD or "").strip(" \"'")
    from_email = (settings.MAILTRAP_FROM_EMAIL or "nao-responda@nivelo.app").strip(" \"'")
    from_name = (settings.MAILTRAP_FROM_NAME or "Nivelo").strip(" \"'")

    html_content = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
      <meta charset="utf-8">
      <style>
        body {{
          font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
          background-color: #141414;
          color: #ffffff;
          padding: 20px;
          margin: 0;
        }}
        .card {{
          background-color: #1f1f1f;
          max-width: 520px;
          margin: 0 auto;
          padding: 32px;
          border-radius: 12px;
          border: 1px solid #333333;
          box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
        }}
        .logo {{
          font-size: 24px;
          font-weight: 700;
          color: #e50914;
          margin-bottom: 20px;
          display: flex;
          align-items: center;
          gap: 8px;
        }}
        h2 {{
          color: #ffffff;
          margin-top: 0;
          font-size: 20px;
        }}
        p {{
          color: #cccccc;
          line-height: 1.6;
          font-size: 15px;
        }}
        .btn-container {{
          text-align: center;
          margin: 30px 0;
        }}
        .btn {{
          display: inline-block;
          background-color: #e50914;
          color: #ffffff !important;
          padding: 14px 28px;
          text-decoration: none;
          border-radius: 6px;
          font-weight: 600;
          font-size: 16px;
        }}
        .link-box {{
          background-color: #141414;
          padding: 12px;
          border-radius: 6px;
          word-break: break-all;
          font-size: 12px;
          color: #e50914;
        }}
        .footer {{
          font-size: 12px;
          color: #777777;
          margin-top: 30px;
          border-top: 1px solid #2e2e2e;
          padding-top: 16px;
          line-height: 1.5;
        }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="logo">Nivelo</div>
        <h2>Olá, {safe_name}!</h2>
        <p>Recebemos uma solicitação para redefinir a sua senha de acesso ao <strong>Nivelo</strong>.</p>
        <p>Clique no botão abaixo para escolher uma nova senha. <strong>Atenção: este link expira em {settings.RESET_TOKEN_EXPIRE_MINUTES} minutos</strong> e só pode ser utilizado uma única vez.</p>

        <div class="btn-container">
          <a href="{reset_url}" target="_blank" class="btn">Redefinir Minha Senha</a>
        </div>

        <p style="font-size: 13px; color: #999999;">Caso o botão não funcione, copie e cole o endereço abaixo no seu navegador:</p>
        <div class="link-box">{reset_url}</div>

        <div class="footer">
          <p>Se você não solicitou a redefinição de senha, nenhuma ação é necessária. Sua senha atual permanecerá segura.</p>
          <p>© 2026 Nivelo — diário de obra</p>
        </div>
      </div>
    </body>
    </html>
    """

    text_content = (
        f"Olá, {user_name}!\n\n"
        f"Recebemos uma solicitação para redefinir sua senha no Nivelo.\n"
        f"Acesse o link a seguir para criar uma nova senha (válido por {settings.RESET_TOKEN_EXPIRE_MINUTES} minutos):\n"
        f"{reset_url}\n\n"
        f"Se você não solicitou esta alteração, ignore este e-mail.\n"
    )

    if not smtp_user or not smtp_pass:
        if settings.EMAIL_LOG_LINK_WITHOUT_SMTP:
            logger.warning("SMTP não configurado; link de redefinição (modo dev): %s", reset_url)
            return True
        raise EmailNotConfiguredError(
            "MAILTRAP_USERNAME/MAILTRAP_PASSWORD não configurados; e-mail de redefinição não enviado"
        )

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{from_email}>"
        msg["To"] = to_email

        msg.attach(MIMEText(text_content, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_email, [to_email], msg.as_string())

        logger.info("E-mail de redefinição enviado via %s para o usuário %s", smtp_host, to_email)
        return True
    except Exception:
        logger.exception("Falha ao enviar e-mail de redefinição via %s:%s", smtp_host, smtp_port)
        raise


def _enviar_email(to_email: str, subject: str, texto: str, html_content: str, link_para_log: str) -> bool:
    """Envia por SMTP (Mailtrap). Sem credenciais: no modo dev registra o link; senão, erro explícito."""
    smtp_host = (settings.MAILTRAP_HOST or "sandbox.smtp.mailtrap.io").strip(" \"'")
    try:
        smtp_port = int(str(settings.MAILTRAP_PORT).strip(" \"'"))
    except Exception:
        smtp_port = 2525
    smtp_user = (settings.MAILTRAP_USERNAME or "").strip(" \"'")
    smtp_pass = (settings.MAILTRAP_PASSWORD or "").strip(" \"'")
    from_email = (settings.MAILTRAP_FROM_EMAIL or "nao-responda@nivelo.app").strip(" \"'")
    from_name = (settings.MAILTRAP_FROM_NAME or "Nivelo").strip(" \"'")

    if not smtp_user or not smtp_pass:
        if settings.EMAIL_LOG_LINK_WITHOUT_SMTP:
            logger.warning("SMTP não configurado; link (modo dev): %s", link_para_log)
            return True
        raise EmailNotConfiguredError("MAILTRAP_USERNAME/MAILTRAP_PASSWORD não configurados; e-mail não enviado")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email
    msg.attach(MIMEText(texto, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))
    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_email, [to_email], msg.as_string())
    except Exception:
        logger.exception("Falha ao enviar e-mail via %s:%s", smtp_host, smtp_port)
        raise
    logger.info("E-mail '%s' enviado via %s", subject, smtp_host)
    return True


PAPEL_NO_CONVITE = {"encarregado": "encarregado", "cliente": "cliente da obra"}


def send_convite_email(to_email: str, token: str, empresa_nome: str, papel: str, convidado_por: str) -> bool:
    """Convite para entrar numa empresa. O link leva o token em claro; o banco guarda só o hash."""
    base = (settings.APP_BASE_URL or settings.CATALOGO_URL or "http://localhost:8000").strip(" \"'").rstrip("/")
    link = f"{base}/convite?token={token}"
    empresa = html.escape(empresa_nome)
    quem = html.escape(convidado_por)
    como = PAPEL_NO_CONVITE.get(papel, papel)
    horas = settings.CONVITE_VALIDADE_HORAS

    html_content = f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; background: #141414; color: #ffffff; padding: 20px;">
  <div style="max-width: 520px; margin: 0 auto; background: #1f1f1f; padding: 32px; border-radius: 12px;">
    <h2 style="margin-top: 0;">Você foi convidado para o Nivelo</h2>
    <p><strong>{quem}</strong> convidou você para acompanhar as obras de <strong>{empresa}</strong> como <strong>{como}</strong>.</p>
    <p><a href="{link}" style="display: inline-block; background: #d1a441; color: #141414; padding: 12px 20px;
       border-radius: 6px; text-decoration: none; font-weight: bold;">Aceitar convite</a></p>
    <p style="font-size: 13px; color: #999999;">O convite vale por {horas} horas e só pode ser usado uma vez.
       Se o botão não funcionar, copie este endereço: {link}</p>
    <p style="font-size: 12px; color: #777777;">Se você não esperava este convite, ignore este e-mail.</p>
  </div>
</body></html>"""
    texto = (
        f"{convidado_por} convidou você para acompanhar as obras de {empresa_nome} como {como}.\n"
        f"Aceite em até {horas} horas (uso único): {link}\n\n"
        "Se você não esperava este convite, ignore este e-mail.\n"
    )
    return _enviar_email(to_email, f"Convite de {empresa_nome} no Nivelo", texto, html_content, link)


def send_aviso_de_inadimplencia_email(to_email: str, empresa_nome: str) -> bool:
    """O pagamento falhou: a empresa está com os limites do Free até regularizar."""
    base = (settings.APP_BASE_URL or settings.CATALOGO_URL or "http://localhost:8000").strip(" \"'").rstrip("/")
    link = f"{base}/assinatura"
    empresa = html.escape(empresa_nome)
    html_content = f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; background: #F4F2EE; color: #1B1E1C; padding: 20px;">
  <div style="max-width: 520px; margin: 0 auto; background: #FFFFFF; padding: 32px; border-radius: 12px;">
    <h2 style="margin-top: 0;">Não conseguimos cobrar a assinatura</h2>
    <p>O pagamento da assinatura de <strong>{empresa}</strong> falhou. Enquanto ele não for regularizado,
       a empresa fica com os limites do plano Free. Nenhum diário é apagado.</p>
    <p><a href="{link}" style="display: inline-block; background: #2F6B4F; color: #FFFFFF; padding: 12px 20px;
       border-radius: 6px; text-decoration: none; font-weight: bold;">Atualizar pagamento</a></p>
  </div>
</body></html>"""
    texto = (
        f"O pagamento da assinatura de {empresa_nome} falhou. Enquanto ele não for regularizado, a empresa "
        f"fica com os limites do plano Free. Nenhum diário é apagado.\nAtualize em: {link}\n"
    )
    return _enviar_email(to_email, f"Pagamento não aprovado — {empresa_nome}", texto, html_content, link)
