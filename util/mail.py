import os
from server import app, mail, Message
from threading import Thread
import logging

base_url = os.environ.get('ALLOW_FE_URLS')
logger = logging.getLogger(__name__)

def mail_verifi(recipient,token):

    mail_subject = 'verification for your register'.upper()
    mail_recipients = [recipient]
    mail_html = f'''
                <h3> Thank you for join in! Please Click <b><a href='{base_url}/verify?token={token}'>Here</a></b> to complete the registeration.</h3>
                <h3> This mail will become invalid after 10 minutes. </h3>
                '''
    msg = Message(
        subject=mail_subject,
        recipients=mail_recipients)
    msg.html = mail_html
    thr = Thread(target=send_async_mail,args=[app, msg])
    thr.start()
    return 

def mail_psw(recipient,token):

    mail_subject = 'reset your password'.upper()
    mail_recipients = [recipient]
    mail_html = f'''
                <h3>Hello <b>{str(recipient)}</b> !</h3> 
                <h3> Click <a href=\'{base_url}/psw_reset?token={token}\'>Here</a> to reset your passwords.</h3>
                <h3> This mail will become invalid after 10 minutes. </h3>
                '''
    msg = Message(
        subject=mail_subject,
        recipients=mail_recipients)
    msg.html = mail_html
    thr = Thread(target=send_async_mail,args=[app, msg])
    thr.start()
    return 

def send_async_mail(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as e:
            logger.error(f'信件寄送錯誤>> {e}',exc_info=True)