import requests, bs4


def login(session, config):
    r = session.get('https://www.mon-compte.bouyguestelecom.fr/cas/login')
    r.raise_for_status()
    html = bs4.BeautifulSoup(r.text, "html.parser")
    token = html.select('#log_cta > input[name="lt"]')[0].get('value')

    r = session.post('https://www.mon-compte.bouyguestelecom.fr/cas/login', data={
        'username': config.get('bouygues_username', ''),
        'password': config.get('bouygues_password', ''),
        'lt': token,
        'rememberMe': 'true',
        '_rememberMe': 'on',
        'execution': 'e1s1',
        '_eventId': 'submit'
    })
    r.raise_for_status()
    return session


def send(config, message):
    session = login(requests.Session(), config)

    r = session.get('https://www.secure.bbox.bouyguestelecom.fr/services/SMSIHD/sendSMS.phtml')
    r.raise_for_status()

    r = session.post('https://www.secure.bbox.bouyguestelecom.fr/services/SMSIHD/confirmSendSMS.phtml', data={
        'fieldMsisdn': ";".join(config.get('notify_numbers', [])),
        'fieldMessage': message,
        'Verif.x': 54,
        'Verif.y': 12
    })
    r.raise_for_status()

    r = session.get('https://www.secure.bbox.bouyguestelecom.fr/services/SMSIHD/resultSendSMS.phtml')
    r.raise_for_status()
