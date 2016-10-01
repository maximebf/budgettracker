import requests, time, os, json, datetime
from .data import dump_transactions, load_transactions, extract_inter_account_transactions
from .budget import budgetize, IncomeSource, RecurringExpense, SavingsGoal
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


def create_adapter_and_session_from_config(config):
    adapter = load_adapter('bank_adapters', config['bank_adapter'])
    session = create_logged_in_session(adapter.login, config['bank_username'], config['bank_password'])
    return adapter, session


def save_balance(adapter, session, filename='balance'):
    balance = sum([acc.amount for acc in adapter.fetch_accounts(session)])
    with open(filename, 'w') as f:
        f.write(str(balance))
    return balance


def load_balance(adapter=None, session=None, filename='balance', refresh=False):
    if refresh and adapter and session:
        return save_balance(adapter, session, filename)
    if os.path.exists(filename):
        with open(filename) as f:
            return float(f.read())
    return None


def get_transactions_of_month_dump_filename(date, directory=None, filename=None):
    if not filename:
        filename = date.replace(day=1).strftime("%Y-%m.json")
    if directory:
        filename = os.path.join(directory, filename)
    return filename


def save_transactions_of_month(date, adapter, session, filename=None, directory=None):
    filename = get_transactions_of_month_dump_filename(date, directory, filename)
    if not os.path.exists(os.path.dirname(filename)):
        os.makedirs(os.path.dirname(filename))
    start_date = date.replace(day=1)
    end_date = start_date + monthdelta(1)
    transactions = adapter.fetch_transactions_from_all_accounts(session, start_date, end_date)
    dump_transactions(transactions, filename)
    return transactions


def load_transactions_of_month(date, refresh=False, adapter=None, session=None, filename=None, directory=None):
    filename = get_transactions_of_month_dump_filename(date, directory, filename)
    start_date = date.replace(day=1)
    end_date = start_date + monthdelta(1)
    if refresh and adapter and session:
        return save_transactions_of_month(date, adapter, session, filename)
    if os.path.exists(filename):
        return load_transactions(filename)
    return None


def make_budget_from_config(transactions, config):
    if 'inter_account_labels_out' in config and 'inter_account_labels_in' in config:
        _, transactions = extract_inter_account_transactions(transactions,
                config['inter_account_labels_out'], config['inter_account_labels_in'])
    income_sources = map(IncomeSource.from_dict, config.get('income_sources', []))
    recurring_expenses = map(RecurringExpense.from_dict, config.get('recurring_expenses', []))
    savings_goals = map(SavingsGoal.from_dict, config.get('savings_goals', []))
    return budgetize(transactions, income_sources, recurring_expenses, savings_goals)


def load_budget_of_month_from_config(config, date, refresh=False, adapter=None, session=None):
    if refresh and not adapter and not session:
        adapter, session = create_adapter_and_session_from_config(config)
    transactions = load_transactions_of_month(date, refresh=refresh, adapter=adapter,
        session=session, directory=config.get('transactions_dir'))
    if transactions is None:
        return None
    return make_budget_from_config(transactions, config)


def notify_using_config(config, message):
    print message
    if config.get('notify_adapter'):
        adapter = load_adapter('notify_adapters', config['notify_adapter'])
        session = adapter.login(requests.Session(), config['notify_username'], config['notify_password'])
        adapter.send(session, config['notify_numbers'], message)


def update_local_data(config, notify=True, date=None, adapter=None, session=None):
    if not adapter:
        adapter, session = create_adapter_and_session_from_config(config)

    if not date:
        if datetime.date.today().day <= 5:
            # if we are still in the early days of a new month, keep updating the previous month
            update_local_data(config, False, datetime.date.today() - monthdelta(1), adapter, session)
        date = datetime.date.today().replace(day=1)

    prev_budget = load_budget_of_month_from_config(config, date)
    budget = load_budget_of_month_from_config(config, date, refresh=True, adapter=adapter, session=session)
    save_balance(adapter, session)

    if notify and prev_budget:
        if config.get('notify_remaining') and prev_budget.expected_remaining > config['notify_remaining'] and budget.expected_remaining <= config['notify_remaining']:
            notify_using_config(config, 'BUDGET: /!\ LOW SAFE TO SPEND: %se' % budget.expected_remaining)
        elif config.get('notify_delta') and (prev_budget.expected_remaining - budget.expected_remaining) > config['notify_delta']:
            notify_using_config(config, 'BUDGET: Remaining funds: %se' % budget.expected_remaining)