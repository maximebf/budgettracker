import smtplib


def send(config, message):
    from_email = config.get('notify_from_email') or config.get('notify_username', 'no-reply@budgettracker')
    body = "\r\n".join([
        "From: %s" % from_email,
        "To: %s" % ', '.join(config['notify_emails']),
        "Subject: Notification from BudgetTracker",
        "",
        message
    ])

    try:
        server = smtplib.SMTP(config['notify_host'])
        server.ehlo()
        if config.get('notify_tls'):
            server.starttls()
            server.ehlo()
        if 'notify_username':
            server.login(config['notify_username'], config['notify_password'])
        server.sendmail(from_email, config['notify_emails'], body)
        server.quit()
    except Exception as e:
        print e