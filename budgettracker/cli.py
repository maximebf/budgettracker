# -*- coding: utf-8 -*-
from .helpers import (load_config, update_local_data, load_yearly_budgets_from_config, notify_using_config,
                      compute_yearly_savings_goals_from_config, compute_monthly_categories_from_config,
                      rematch_categories, get_storage_from_config)
from .storage import get_storage
import datetime, sys, os, json
from getopt import getopt


config = load_config()
storage = get_storage_from_config(config)
commands = {}


def command(options='', long_options=None):
    def decorator(func):
        commands[func.__name__] = (func, options, long_options or [])
        return func
    return decorator


@command('', ['month=', 'year=', 'reset'])
def update(filename=None, month=None, year=None, reset=False):
    date = None
    if month or year:
        if not month:
            month = datetime.date.today().month
        if not year:
            year = datetime.date.today().year
        date = datetime.date(int(year), int(month), 1)
    update_local_data(config, date=date, filename=filename, reset=reset)


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

    balance = sum([a.amount for a in storage.load_accounts()])
    budgets = load_yearly_budgets_from_config(config, date, storage=storage)
    categories = compute_monthly_categories_from_config(config, date, storage=storage)
    goals = compute_yearly_savings_goals_from_config(config, date, storage=storage)
    budget = budgets.get_from_date(date)
    
    cur = config.get('currency', '$')
    tx_formatter = lambda tx: tx.to_str(cur)
    category_formatter = lambda c: "%s = %s%s (%s%%)" % (c.name or 'Uncategorized', c.amount, cur, c.pct)
    goal_formatter = lambda g: "%s: %s%s / %s%s (%s%%) [used=%s%s saved=%s%s remaining=%s%s]" % (
        g.label, g.completed_amount, cur, g.target, cur, g.completed_pct, g.used, cur, g.saved, cur, g.remaining, cur)

    print budget.month.strftime("%B %Y")
    print 
    print u"Income = %s%s (expected = %s%s):" % (budget.income, cur, budget.expected_income, cur)
    print u"\n".join(map(tx_formatter, budget.income_transactions))
    print
    print u"Planned expenses = %s%s (expected = %s%s):" % (budget.planned_expenses, cur, budget.expected_planned_expenses, cur)
    print u"\n".join(map(tx_formatter, budget.planned_expenses_transactions))
    print
    print u"Expenses = %s%s:" % (budget.expenses, cur)
    print u"\n".join(map(tx_formatter, budget.expenses_transactions))
    print
    if categories:
        print u"Categories:"
        print u"\n".join(map(category_formatter, categories))
        print
    if goals:
        print u"Savings goals:"
        print u"\n".join(map(goal_formatter, goals))
        print
    print "-----------------------------------------"
    print budget.month.strftime("%B %Y")
    print "-----------------------------------------"
    print u"Available             = {0}{1}".format(balance, cur)
    print u"Yearly savings        = {0}{1}".format(budgets.savings, cur)
    print "-----------------------------------------"
    print u"Income                = {0}{1} ({2:+}{3})".format(budget.expected_income, cur, budget.income - budget.expected_income, cur)
    print u"Planned expenses      = {0}{1} ({2}{3})".format(budget.expected_planned_expenses, cur, budget.planned_expenses, cur)
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
    def iterator(transactions):
        if tx.account == prev_id:
            return tx.update(account=new_id)
        return tx
    storage.iter_all_transactions_for_update(iterator)


@command()
def remap_category(old_category, new_category):
    def iterator(transactions):
        return tx.update(categories=map(
            lambda c: new_category if c == old_category else c,
            tx.categories or []
        ))
    storage.iter_all_transactions_for_update(iterator)


command()(rematch_categories)


@command('', ['new-storage-dir='])
def migrate_storage(new_storage, new_storage_dir=None):
    old_storage = get_storage_from_config(config)
    new_storage = get_storage(new_storage)(dict(config, storage_dir=new_storage_dir or config.get('storage_dir')))

    new_storage.save_accounts(old_storage.load_accounts())
    for date in old_storage.iter_months():
        transactions = old_storage.load_monthly_transactions(date)
        new_storage.save_monthly_transactions(date, transactions)
    

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
    func(*args, **{k.strip('-').replace('-', '_'): v if v else True for k, v in kwargs})