# -*- coding: utf-8 -*-
from .data import format_transaction, dump_transactions, load_transactions
from .utils import load_config, load_adapter, create_logged_in_session, make_budget_from_config, load_budget_from_config, load_balance
import requests, datetime, sys, os


config = load_config()


def notify(message):
    print message
    if config.get('notify_adapter'):
        adapter = load_adapter('notify_adapters', config['notify_adapter'])
        session = adapter.login(requests.Session(), config['notify_username'], config['notify_password'])
        adapter.send(session, config['notify_numbers'], message)


def update():
    date = datetime.date.today().replace(day=1)
    filename = os.path.join(config['transactions_dir'], date.strftime('%Y-%m.json'))
    prev_budget = None
    if os.path.exists(filename):
        transactions = load_transactions(filename)
        prev_budget = make_budget_from_config(transactions, config)

    adapter = load_adapter('bank_adapters', config['bank_adapter'])
    session = create_logged_in_session(adapter.login, config['bank_username'], config['bank_password'])
    transactions = adapter.fetch_transactions_from_all_accounts(session, date)
    dump_transactions(transactions, filename)

    if prev_budget:
        budget = make_budget_from_config(transactions, config)
        if config.get('notify_balance') and prev_budget.balance > config['notify_balance'] and budget.balance <= config['notify_balance']:
            notify(u'BUDGET: /!\ LOW BALANCE: %se' % budget.balance)
        elif config.get('notify_delta') and (prev_budget.remaining - budget.remaining) > config['notify_delta']:
            notify(u'BUDGET: Remaining funds: %se' % budget.remaining)


def situation():
    if len(sys.argv) > 2:
        month = int(sys.argv[2])
    else:
        month = datetime.date.today().month
    if len(sys.argv) > 3:
        year = int(sys.argv[3])
    else:
        year = datetime.date.today().year
    date = datetime.date(year, month, 1)
    budget, adapter, session = load_budget_from_config(config, date)
    print date.strftime("%B %Y")
    print 
    print "Income = %s€" % budget.income
    print "\n".join(map(format_transaction, budget.income_transactions))
    print
    print "Recurring expenses = %s€" % budget.recurring_expenses
    print "\n".join(map(format_transaction, budget.recurring_expenses_transactions))
    print
    print "Expenses = %s€" % budget.expenses
    print "\n".join(map(format_transaction, budget.expenses_transactions))
    print
    print "-----------------------------------------"
    print date.strftime("%B %Y")
    print "-----------------------------------------"
    print "Balance              = %s€" % load_balance(adapter, session)
    print "Balance this month   = %s€" % budget.balance
    print "-----------------------------------------"
    print "Income               = %s€ / %s€" % (budget.income, budget.expected_income)
    print "Recurring expenses   = %s€ / %s€" % (budget.recurring_expenses, budget.expected_recurring_expenses)
    print "Expected available   = %s€" % budget.expected_available
    print "-----------------------------------------"
    print "Expenses             = %s€" % budget.expenses
    print "Savings              = %s€ / %s€ / %s€" % (budget.savings, budget.expected_savings, budget.savings_goal)
    print "Remaining            = %s€" % (budget.expected_remaining)


command = "situation"
if len(sys.argv) > 1:
    command = sys.argv[1]

if command not in locals():
    print "Command not found"
    sys.exit(1)

locals()[command]()
