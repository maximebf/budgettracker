import requests, time, os, json, datetime
from .data import dump_transactions, load_transactions, TransactionList
from .filters import budgetize, extract_inter_account_transactions
from monthdelta import monthdelta


CONFIG_FILENAME = 'config.json'


def load_config(filename=CONFIG_FILENAME):
    with open(filename) as f:
        return json.load(f)


def load_adapter(package, name):
    return getattr(__import__(package + '.' + name, globals(), locals(), [], -1), name)


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


def load_balance(adapter=None, session=None, filename='balance', refresh_after=86400):
    exp = time.time() - refresh_after if refresh_after is not None else None
    if not os.path.exists(filename) or (exp and os.path.getmtime(filename) < exp):
        if adapter and session:
            balance = sum([acc.amount for acc in adapter.fetch_accounts(session)])
            with open(filename, 'w') as f:
                f.write(str(balance))
        else:
            balance = 0
    else:
        with open(filename) as f:
            balance = float(f.read())
    return balance


def load_transactions_of_month(date, adapter=None, session=None, filename=None, refresh_after=86400, directory=None):
    start_date = date.replace(day=1)
    end_date = start_date + monthdelta(1)
    exp = time.time() - refresh_after if refresh_after is not None else None
    if end_date < datetime.date.today().replace(day=1):
        # we don't refresh previous months, even if file is "expired"
        exp = None
    if not filename:
        filename = start_date.strftime("%Y-%m.json")
    if directory:
        filename = os.path.join(directory, filename)
    if not os.path.exists(os.path.dirname(filename)):
        os.makedirs(os.path.dirname(filename))

    if not os.path.exists(filename) or (exp and os.path.getmtime(filename) < exp):
        if adapter and session:
            transactions = adapter.fetch_transactions_from_all_accounts(session, start_date, end_date)
            dump_transactions(transactions, filename)
        else:
            transactions = TransactionList()
    else:
        transactions = load_transactions(filename)

    return transactions


def make_budget_from_config(transactions, config):
    _, transactions = extract_inter_account_transactions(transactions,
            config['inter_account_labels_out'], config['inter_account_labels_in'])
    return budgetize(transactions, config.get('expected_income', 0), config.get('expected_recurring_expenses', 0),
        config.get('recurring_expenses_labels', []), config.get('savings_goal', 0))


def load_budget_from_config(config, date):
    adapter = load_adapter('bank_adapters', config['bank_adapter'])
    session = create_logged_in_session(adapter.login, config['bank_username'], config['bank_password'])
    transactions = load_transactions_of_month(date, adapter, session, directory=config.get('transactions_dir'))
    return make_budget_from_config(transactions, config), adapter, session