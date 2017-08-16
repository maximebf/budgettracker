from ..utils import load_adapter
import requests, time, os, json, codecs


__all__ = ('load_adapter', 'create_logged_in_session', 'create_adapter_and_session_from_config')


def create_logged_in_session(login_adapter, identifier, password, reuse=True, filename='session.json'):
    session = requests.Session()
    exp = time.time() - 1800 # cookie jar expires after 30min

    if reuse and os.path.exists(filename) and os.path.getmtime(filename) > exp:
        with open(filename) as f:
            cookies = json.load(f)
        session.cookies.update(cookies)
    else:
        login_adapter(session, identifier, password)
        with open(filename, 'w') as f:
            json.dump(session.cookies.get_dict(), f)

    return session


def create_adapter_and_session_from_config(config, filename=None):
    adapter = load_adapter('bank_adapters', config['bank_adapter'])
    if adapter.ADAPTER_TYPE == 'web':
        session = create_logged_in_session(adapter.login, config['bank_username'], config['bank_password'])
    elif adapter.ADAPTER_TYPE == 'file':
        if not filename:
            raise Exception('Missing file')
        session = codecs.open(filename)
    return adapter, session