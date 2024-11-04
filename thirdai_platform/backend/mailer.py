import logging
import os

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# mailer which can be used to send mails from our webserver.


def mailer(to, subject, body, cc_emails=None):
    from_email = "ThirdAI <platform@thirdai.com>"
    message = Mail(
        from_email=from_email, to_emails=to, subject=subject, html_content=body
    )
    if cc_emails:
        for cc_email in cc_emails:
            message.add_cc(cc_email)
    try:
        sendgrid_key = os.getenv(
            "SENDGRID_KEY",
            "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",
        )
        sg = SendGridAPIClient(sendgrid_key)
        response = sg.send(message)
        if response.status_code != 200:
            logging.error(f"Failed to send the mail: {response.body}")

    except Exception as e:
        logging.error(e)
        raise e
