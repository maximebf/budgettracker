import time, os, datetime, codecs, yaml
from .data import (extract_inter_account_transactions, filter_transactions_period, update_transactions,
                   update_accounts as _update_accounts, period_to_months)
from .budget import budgetize, IncomeSource, PlannedExpense, BudgetGoal, compute_budget_goals
from .categories import compute_categories, Category, match_categories
from .bank_adapters import get_bank_adapter
from .storage import get_storage
from monthdelta import monthdelta
from importlib import import_module


ROOT_DIR = os.environ.get('BUDGET_DIR', '.')
CONFIG_FILENAME = os.environ.get('BUDGET_CONFIG', os.path.join(ROOT_DIR, 'config.yaml'))


def get_bank_adapter_from_config(config, filename=None):
    return get_bank_adapter(config.get('bank_adapter', 'csv'))(config, filename)


def get_storage_from_config(config):
    return get_storage(config.get('storage', 'csv'))(config)


def load_config(filename=CONFIG_FILENAME):
    config = {}
    if os.path.exists(filename):
        with open(filename) as f:
            config = yaml.load(f)
    config = {k.lower(): v for k, v in config.items()}
    for k, v in os.environ.items():
        if k.startswith('BUDGET_') and k != 'BUDGET_CONFIG':
            config[k[7:].lower()] = v
    return config


def save_config(config, filename=CONFIG_FILENAME):
    with codecs.open(filename, 'w') as f:
        yaml.safe_dump(config, f, default_flow_style=False)


def budgetize_from_config(config, transactions, start_date, end_date, compute_budget_goals=True, storage=None):
    if config.get('inter_account_labels_out') and config.get('inter_account_labels_in'):
        _, transactions = extract_inter_account_transactions(transactions,
                config['inter_account_labels_out'], config['inter_account_labels_in'])

    income_sources = map(IncomeSource.from_dict, config.get('income_sources', []))
    planned_expenses = map(PlannedExpense.from_dict, config.get('planned_expenses', []))
    income_delay = config.get('income_delay', 0)

    if compute_budget_goals:
        budget_goals, _ = compute_yearly_budget_goals_from_config(config, start_date, storage)
    else:
        budget_goals = map(BudgetGoal.from_dict, config.get('budget_goals', []))

    return budgetize(transactions, start_date, end_date, income_sources,
        planned_expenses, budget_goals, income_delay)


def load_monthly_budget_from_config(config, date, storage=None):
    if not storage:
        storage = get_storage_from_config(config)
    start_date = date.replace(day=1)
    end_date = start_date + monthdelta(1)
    transactions = storage.load_monthly_transactions(start_date)
    if config.get('income_delay'):
        transactions.extend(storage.load_monthly_transactions(end_date))
    return budgetize_from_config(config, transactions, start_date, end_date)[0]


def load_yearly_budgets_from_config(config, date, compute_budget_goals=True, storage=None):
    if not storage:
        storage = get_storage_from_config(config)
    start_date = date.replace(day=1, month=1)
    end_date = start_date.replace(year=start_date.year+1)
    if start_date.year <= datetime.date.today().year:
        end_date = min(datetime.date.today().replace(day=1) + monthdelta(1), end_date)

    transactions = storage.load_yearly_transactions(date)
    if config.get('income_delay'):
        transactions.extend(storage.load_monthly_transactions(end_date))

    return budgetize_from_config(config, transactions, start_date, end_date, compute_budget_goals)


def compute_yearly_budget_goals_from_config(config, date, storage=None, debug=False):
    return compute_budget_goals(
        load_yearly_budgets_from_config(config, date, False, storage),
        map(BudgetGoal.from_dict, config.get('budget_goals', [])),
        debug=debug
    )


def compute_monthly_categories_from_config(config, date, storage=None):
    if not storage:
        storage = get_storage_from_config(config)
    categories = map(Category.from_dict, config.get('categories', []))
    transactions = storage.load_monthly_transactions(date)
    return compute_categories(transactions, categories)


def update_monthly_transactions(storage, adapter, date, reset=False):
    start_date = date.replace(day=1)
    end_date = start_date + monthdelta(1)

    transactions = adapter.fetch_transactions_from_all_accounts(start_date, end_date)
    if not reset:
        old_transactions = storage.load_monthly_transactions(date)
        transactions = update_transactions(old_transactions, transactions)

    storage.save_monthly_transactions(date, transactions)
    return transactions


def update_accounts(storage, adapter, reset=False):
    accounts = list(adapter.fetch_accounts())
    if not reset:
        old_accounts = storage.load_accounts()
        accounts = _update_accounts(old_accounts, accounts)
    storage.save_accounts(accounts)
    return accounts


def update_local_data(config, notify=True, date=None, storage=None, adapter=None, filename=None, reset=False):
    if not adapter:
        adapter = get_bank_adapter_from_config(config, filename)
    if not storage:
        storage = get_storage_from_config(config)

    if not date:
        if datetime.date.today().day <= 5:
            # if we are still in the early days of a new month, keep updating the previous month
            update_local_data(config, False, datetime.date.today() - monthdelta(1), adapter, session)
        date = datetime.date.today().replace(day=1)
    elif date < datetime.date.today().replace(day=1):
        notify = False

    prev_budget = load_monthly_budget_from_config(config, date, storage)

    update_monthly_transactions(storage, adapter, date, reset)
    update_accounts(storage, adapter, reset)

    budget = load_monthly_budget_from_config(config, date, storage)

    if notify:
        if config.get('notify_remaining') and prev_budget.expected_remaining > config['notify_remaining'] and budget.expected_remaining <= config['notify_remaining']:
            notify_using_config(config, 'BUDGET: /!\ LOW SAFE TO SPEND: %s' % budget.expected_remaining)
        elif config.get('notify_delta') and (prev_budget.expected_remaining - budget.expected_remaining) > config['notify_delta']:
            notify_using_config(config, 'BUDGET: Remaining funds: %s' % budget.expected_remaining)

        categories = compute_monthly_categories_from_config(config, date, storage)
        for category in categories:
            if category.has_warning:
                notify_using_config(config, 'BUDGET: /!\ CATEGORY WARNING: %s (%s / %s)' % (
                    category.name, category.amount, category.warning_threshold))


def rematch_categories(config, storage=None):
    if not storage:
        storage = get_storage_from_config(config)
    categories = map(Category.from_dict, config.get('categories', []))
    def iterator(tx):
        return tx.update(
            categories=list(set(tx.categories or []) | set(match_categories(categories, tx.label))))
    storage.iter_all_transactions_for_update(iterator)


def notify_using_config(config, message):
    print message
    if config.get('notify_adapter'):
        adapter = import_module('budgettracker.notify_adapters.' + config['notify_adapter'])
        adapter.send(config, message)


def create_amount_formatter(config):
    def formatter(amount, show_sign=False):
        sign = ''
        if show_sign or amount < 0:
            sign = '+' if amount >= 0 else '-'
            amount = abs(amount)
        return config.get('amount_format', '{sign}${amount:.2f}').format(sign=sign, amount=amount)
    return formatter
