# -*- coding: utf-8 -*-
from .data import dump_transactions, load_transactions
from .helpers import (load_config, load_adapter, create_adapter_and_session_from_config, save_balance,
                      load_balance, load_budget_of_month_from_config, update_local_data)
import requests, datetime, sys, os
from getopt import getopt


config = load_config()
commands = {}


def command(options='', long_options=None):
    def decorator(func):
        commands[func.__name__] = (func, options, long_options or [])
        return func
    return decorator


@command()
def update():
    update_local_data(config)


@command('', ['update'])
def show(month=None, year=None, refresh=False):
    if not month:
        month = datetime.date.today().month
    if not year:
        year = datetime.date.today().year
    date = datetime.date(int(year), int(month), 1)
    is_current_month = datetime.date.today().replace(day=1) == date

    if refresh:
        update_local_data(config)

    balance = load_balance()
    budget = load_budget_of_month_from_config(config, date)

    print date.strftime("%B %Y")
    print 
    print "Income = %s€" % budget.income
    print u"\n".join(map(unicode, budget.income_transactions))
    print
    print "Recurring expenses = %s€" % budget.recurring_expenses
    print u"\n".join(map(unicode, budget.recurring_expenses_transactions))
    print
    print "Expenses = %s€" % budget.expenses
    print u"\n".join(map(unicode, budget.expenses_transactions))
    print
    print "-----------------------------------------"
    print date.strftime("%B %Y")
    print "-----------------------------------------"
    print "Available            = {0}€".format(balance)
    print "-----------------------------------------"
    print "Income               = {0}€ ({1:+}€)".format(budget.income, budget.income - budget.expected_income)
    print "Recurring expenses   = {0}€ ({1:+}€)".format(budget.expected_recurring_expenses, budget.recurring_expenses)
    print "Expenses             = {0}€".format(budget.expenses)
    if is_current_month:
        print "Real Balance         = {0:+}€".format(budget.expected_real_balance)
        print "-----------------------------------------"
        print "Budget balance       = {0:+}€".format(budget.expected_balance)
        print "Savings              = {0}€ / {1}€".format(budget.expected_savings, budget.savings_goal)
        print "Safe to spend        = {0}€".format(budget.expected_remaining)
    else:
        print "Real Balance         = {0:+}€".format(budget.real_balance)
        print "-----------------------------------------"
        print "Savings              = {0}€ / {1}€".format(budget.savings, budget.savings_goal)
        print "Budget balance       = {0:+}€".format(budget.balance)


@command('', ['port=', 'debug'])
def web(port=5000, debug=False):
    from .web import app
    app.run(port=port, debug=debug)


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