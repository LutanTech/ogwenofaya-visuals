from bs4 import BeautifulSoup
from flask import render_template
from markupsafe import Markup

from emails import mail
from models import Admin, db

def send_mail(user_id, title, message, summary=None):
    is_html = isinstance(message, str) and '<' in message and '>' in message

    user = db.session.get(Admin, user_id)
    
    if user and user.username:
        try:
            if is_html:
                html = message
            else:
                html = render_template(
                    "emails/notification.html",
                    user=user,
                    title=title,
                    message=message,
                    summary=summary or title
                )

            mail.send(user.username, title, html=html)

        except Exception:
            import logging
            logging.exception("Failed to send notification email to %s", user.username)

    # if user and user.email:
    #     try:
    #         if is_html:
    #             html = message
    #         else:
    #             html = render_template(
    #                 "emails/notification.html",
    #                 user=user,
    #                 title=title,
    #                 message=message,
    #                 summary=summary or title
    #             )

    #         mail.send(user.email, title, html=html)

    #     except Exception:
    #         import logging
    #         logging.exception("Failed to send notification email to %s", user.email)

