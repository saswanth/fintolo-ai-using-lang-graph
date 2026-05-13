from __future__ import annotations

import mimetypes
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable


class EmailDeliveryError(ValueError):
    pass


def send_board_email(
    smtp_host: str,
    smtp_port: int,
    smtp_username: str,
    smtp_password: str,
    sender: str,
    recipients: Iterable[str],
    subject: str,
    body: str,
    attachments: Iterable[str],
    use_tls: bool = True,
) -> None:
    recipients_list = [item.strip() for item in recipients if item.strip()]
    if not recipients_list:
        raise EmailDeliveryError("No valid recipients were provided.")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients_list)
    msg.set_content(body)

    for attachment in attachments:
        file_path = Path(attachment)
        if not file_path.exists() or not file_path.is_file():
            continue

        guessed, _ = mimetypes.guess_type(str(file_path))
        if guessed:
            maintype, subtype = guessed.split("/", 1)
        else:
            maintype, subtype = "application", "octet-stream"

        with file_path.open("rb") as handle:
            msg.add_attachment(
                handle.read(),
                maintype=maintype,
                subtype=subtype,
                filename=file_path.name,
            )

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        if use_tls:
            server.starttls()
        server.login(smtp_username, smtp_password)
        server.send_message(msg)
