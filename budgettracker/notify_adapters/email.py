import smtplib


def send(config, message):
    if not config.get('notify_emails'):
        return
        
    from_email = config.get('notify_from_email') or config.get('notify_username', 'no-reply@budgettracker')
    body = "\r\n".join([
        "From: %s" % from_email,
        "To: %s" % ', '.join(config.get('notify_emails', [])),
        "Subject: %s" % message,
        "",
        message
    ])

    try:
        server = smtplib.SMTP(config.get('notify_host', 'localhost'))
        server.ehlo()
        if config.get('notify_tls'):
            server.starttls()
            server.ehlo()
        if config.get('notify_username'):
            server.login(config['notify_username'], config.get('notify_password'))
        server.sendmail(from_email, config['notify_emails'], body)
        server.quit()
    except Exception as e:
        print e