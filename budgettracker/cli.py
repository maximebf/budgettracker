# -*- coding: utf-8 -*-
from .data import dump_transactions, load_transactions
from .utils import load_config
from .helpers import (create_adapter_and_session_from_config, load_accounts_from_config,
                      load_monthly_budget_from_config, update_local_data,
                      load_yearly_budgets_from_config, notify_using_config)
import requests, datetime, sys, os, json
from getopt import getopt


config = load_config()
commands = {}


def command(options='', long_options=None):
    def decorator(func):
        commands[func.__name__] = (func, options, long_options or [])
        return func
    return decorator


@command('', ['month=', 'year='])
def update(filename=None, month=None, year=None):
    date = None
    if month or year:
        if not month:
            month = datetime.date.today().month
        if not year:
            year = datetime.date.today().year
        date = datetime.date(int(year), int(month), 1)
    update_local_data(config, date=date, filename=filename)


@command('', ['month=', 'year=', 'refresh'])
def show(month=None, year=None, refresh=False):
    if not month:
        month = datetime.date.today().month
    if not year:
        year = datetime.date.today().year
    date = datetime.date(int(year), int(month), 1)
    is_current_month = datetime.date.today().replace(day=1) == date

    if refresh:
        update_local_data(config)

    balance = sum([a.amount for a in load_accounts_from_config(config)])
    budgets = load_yearly_budgets_from_config(config, date)
    budget = budgets.get_from_date(date)
    
    cur = config.get('currency', '$')
    tx_formatter = lambda tx: tx.to_str(cur)

    print budget.month.strftime("%B %Y")
    print 
    print u"Income = %s%s (expected = %s%s)" % (budget.income, cur, budget.expected_income, cur)
    print u"\n".join(map(tx_formatter, budget.income_transactions))
    print
    print u"Recurring expenses = %s%s (expected = %s%s)" % (budget.recurring_expenses, cur, budget.expected_recurring_expenses, cur)
    print u"\n".join(map(tx_formatter, budget.recurring_expenses_transactions))
    print
    print u"Expenses = %s%s" % (budget.expenses, cur)
    print u"\n".join(map(tx_formatter, budget.expenses_transactions))
    print
    print "-----------------------------------------"
    print budget.month.strftime("%B %Y")
    print "-----------------------------------------"
    print u"Available             = {0}{1}".format(balance, cur)
    print u"Yearly savings        = {0}{1}".format(budgets.savings, cur)
    print "-----------------------------------------"
    print u"Income                = {0}{1} ({2:+}{3})".format(budget.expected_income, cur, budget.income - budget.expected_income, cur)
    print u"Recurring expenses    = {0}{1} ({2}{3})".format(budget.expected_recurring_expenses, cur, budget.recurring_expenses, cur)
    print u"Expenses              = {0}{1}".format(budget.expenses, cur)
    if is_current_month:
        print u"Real Balance          = {0:+}{1}".format(budget.expected_real_balance, cur)
        print "-----------------------------------------"
        print u"Savings               = {0}{1} / {2}{3}".format(budget.expected_savings, cur, budget.savings_goal, cur)
        print u"Safe to spend         = {0}{1}".format(budget.expected_remaining, cur)
    else:
        print u"Real Balance          = {0:+}{1}".format(budget.real_balance, cur)
        print "-----------------------------------------"
        print u"Savings               = {0}{1} / {2}{3}".format(budget.savings, cur, budget.savings_goal, cur)
        print u"Budget balance        = {0:+}{1}".format(budget.balance, cur)


@command('', ['port=', 'debug'])
def web(port=5000, debug=False):
    from .web import app
    app.run(port=port, debug=debug)


@command()
def notify(message):
    notify_using_config(config, message)


@command()
def remap_account_id(prev_id, new_id):
    data_dir = config.get('data_dir', '.')
    for filename in os.listdir(data_dir):
        pathname = os.path.join(data_dir, filename)
        if not os.path.isfile(pathname):
            continue
        with open(pathname) as f:
            data = json.load(f)
        if filename == 'accounts.json':
            for acc in data:
                if acc['id'] == prev_id:
                    acc['id'] = new_id
        else:
            for tx in data:
                if tx['account'] == prev_id:
                    tx['account'] = new_id
        with open(pathname, 'w') as f:
            json.dump(data, f, indent=2)
    

def main(as_module=False):
    this_module = __package__
    argv = sys.argv[1:]

    if as_module:
        if sys.version_info >= (2, 7):
            name = 'python -m ' + this_module.rsplit('.', 1)[0]
        else:
            name = 'python -m ' + this_module
        sys.argv = ['-m', this_module] + sys.argv[1:]
    else:
        name = None

    if len(argv) == 0:
        print "Missing command. Available: %s" % ", ".join(commands.keys())
        sys.exit(1)
    command = argv.pop(0)
    if command not in commands:
        print "Wrong command!"
        sys.exit(1)
    func, options, long_options = commands[command]
    kwargs, args = getopt(argv, options, long_options)
    func(*args, **{k.strip('-'): v if v else True for k, v in kwargs})