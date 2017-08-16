import requests, time, os, datetime
from .data import (dump_transactions, load_transactions, extract_inter_account_transactions,
                    dump_accounts, load_accounts as _load_accounts, filter_transactions_period)
from .budget import budgetize, IncomeSource, RecurringExpense, SavingsGoal, period_to_months
from .bank_adapters import *
from monthdelta import monthdelta


def get_accounts_filename(directory=None, filename=None):
    if not filename:
        filename = 'accounts.json'
    if directory:
        filename = os.path.join(directory, filename)
    return filename


def save_accounts(adapter, session, directory=None, filename=None):
    accounts = adapter.fetch_accounts(session)
    dump_accounts(accounts, get_accounts_filename(directory, filename))
    return accounts


def load_accounts(adapter=None, session=None, directory=None, filename=None, refresh=False):
    if refresh and adapter and session:
        return save_accounts(adapter, session, directory=directory, filename=filename)
    return _load_accounts(get_accounts_filename(directory, filename))


def load_accounts_from_config(config, *args, **kwargs):
    kwargs['directory'] = config.get('data_dir')
    return load_accounts(*args, **kwargs)


def get_monthly_transactions_filename(date, directory=None, filename=None):
    if not filename:
        filename = date.replace(day=1).strftime("%Y-%m.json")
    if directory:
        filename = os.path.join(directory, filename)
    return filename


def save_monthly_transactions(date, adapter, session, filename=None, directory=None):
    filename = get_monthly_transactions_filename(date, directory, filename)
    if not os.path.exists(os.path.dirname(filename)):
        os.makedirs(os.path.dirname(filename))
    start_date = date.replace(day=1)
    end_date = start_date + monthdelta(1)
    transactions = adapter.fetch_transactions_from_all_accounts(session, start_date, end_date)
    dump_transactions(transactions, filename)
    return transactions


def load_monthly_transactions(date, refresh=False, adapter=None, session=None, filename=None, directory=None):
    filename = get_monthly_transactions_filename(date, directory, filename)
    start_date = date.replace(day=1)
    end_date = start_date + monthdelta(1)
    if refresh and adapter and session:
        return save_monthly_transactions(date, adapter, session, filename)
    if os.path.exists(filename):
        return load_transactions(filename)
    return []


def load_period_transactions(start_date, end_date, directory=None):
    transactions = []
    for date in period_to_months(start_date, end_date):
        transactions.extend(load_monthly_transactions(date, directory=directory))
    return filter_transactions_period(transactions, start_date, end_date)


def load_yearly_transactions(date, directory=None):
    start_date = date.replace(day=1, month=1)
    end_date = start_date.replace(year=start_date.year+1)
    return load_period_transactions(start_date, end_date, directory=directory)


def budgetize_from_config(transactions, start_date, end_date, config):
    if 'inter_account_labels_out' in config and 'inter_account_labels_in' in config:
        _, transactions = extract_inter_account_transactions(transactions,
                config['inter_account_labels_out'], config['inter_account_labels_in'])

    income_sources = map(IncomeSource.from_dict, config.get('income_sources', []))
    income_delay = config.get('income_delay', 0)
    recurring_expenses = map(RecurringExpense.from_dict, config.get('recurring_expenses', []))
    savings_goals = map(SavingsGoal.from_dict, config.get('savings_goals', []))

    return budgetize(transactions, start_date, end_date, income_sources, recurring_expenses,
        savings_goals, income_delay)


def load_monthly_budget_from_config(config, date, refresh=False, adapter=None, session=None, filename=None):
    if refresh and not adapter and not session:
        adapter, session = create_adapter_and_session_from_config(config, filename)

    start_date = date.replace(day=1)
    end_date = start_date + monthdelta(1)
    transactions = load_monthly_transactions(start_date, refresh=refresh, adapter=adapter,
        session=session, directory=config.get('data_dir'))

    if config.get('income_delay'):
        transactions.extend(load_monthly_transactions(end_date, directory=config.get('data_dir')))

    return budgetize_from_config(transactions, start_date, end_date, config)[0]


def load_yearly_budgets_from_config(config, date, include_future_months=False):
    start_date = date.replace(day=1, month=1)
    end_date = start_date.replace(year=start_date.year+1)
    if start_date.year <= datetime.date.today().year:
        end_date = min(datetime.date.today().replace(day=1) + monthdelta(1), end_date)
    transactions = load_yearly_transactions(date, directory=config.get('data_dir'))

    if config.get('income_delay'):
        transactions.extend(load_monthly_transactions(end_date, directory=config.get('data_dir')))

    return budgetize_from_config(transactions, start_date, end_date, config)


def notify_using_config(config, message):
    print message
    if config.get('notify_adapter'):
        adapter = load_adapter('notify_adapters', config['notify_adapter'])
        adapter.send(config, message)


def update_local_data(config, notify=True, date=None, adapter=None, session=None, filename=None):
    if not adapter:
        adapter, session = create_adapter_and_session_from_config(config, filename)

    if not date:
        if datetime.date.today().day <= 5:
            # if we are still in the early days of a new month, keep updating the previous month
            update_local_data(config, False, datetime.date.today() - monthdelta(1), adapter, session)
        date = datetime.date.today().replace(day=1)

    prev_budget = load_monthly_budget_from_config(config, date)
    budget = load_monthly_budget_from_config(config, date, refresh=True, adapter=adapter, session=session)
    save_accounts(adapter, session, directory=config.get('data_dir'))

    if notify:
        if config.get('notify_remaining') and prev_budget.expected_remaining > config['notify_remaining'] and budget.expected_remaining <= config['notify_remaining']:
            notify_using_config(config, 'BUDGET: /!\ LOW SAFE TO SPEND: %se' % budget.expected_remaining)
        elif config.get('notify_delta') and (prev_budget.expected_remaining - budget.expected_remaining) > config['notify_delta']:
            notify_using_config(config, 'BUDGET: Remaining funds: %se' % budget.expected_remaining)