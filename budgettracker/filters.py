import re
from collections import namedtuple
from .data import TransactionList


def filter_transactions(func, transactions):
    return TransactionList(filter(func, transactions))


def filter_out_transactions(transactions, remove_transactions):
    return TransactionList(filter(lambda tx: tx not in remove_transactions, transactions))


def split_income_expenses(transactions):
    income = TransactionList(filter(lambda tx: tx.amount > 0.0, transactions))
    expenses = TransactionList(filter(lambda tx: tx.amount < 0.0, transactions))
    return income, expenses


def extract_inter_account_transactions(transactions, labels_out, labels_in):
    tx_out = {}
    tx_in = {}
    for tx in transactions:
        m = re.match(labels_out, tx.label)
        if m:
            tx_out[m.group('id')] = tx
            continue
        m = re.match(labels_in, tx.label)
        if m:
            tx_in[m.group('id')] = tx

    inter_account_transactions = set()
    for id, tx in tx_out.iteritems():
        if id in tx_in:
            inter_account_transactions.add(tx)
            inter_account_transactions.add(tx_in[id])

    transactions = filter_out_transactions(transactions, inter_account_transactions)
    return inter_account_transactions, transactions


def extract_transactions_by_label(transactions, labels):
    def filter(tx):
        for exp in labels:
            if re.match(exp, tx.label):
                return True
        return False
    matching = filter_transactions(filter, transactions)
    transactions = filter_out_transactions(transactions, matching)
    return matching, transactions


Budget = namedtuple('Budget', ['transactions', 'income_transactions', 'recurring_expenses_transactions',
    'expenses_transactions', 'balance', 'income', 'recurring_expenses', 'expenses', 'savings',  'savings_goal',
    'expected_income', 'expected_recurring_expenses', 'expected_available', 'expected_savings', 'expected_remaining'])


def budgetize(transactions, expected_income=0, expected_recurring_expenses=0, recurring_expenses_labels=None, savings_goal=0):
    income_transactions, expenses_transactions = split_income_expenses(transactions)
    recurring_expenses_transactions, expenses_transactions = extract_transactions_by_label(
        expenses_transactions, recurring_expenses_labels)

    expenses_goal = expected_income - expected_recurring_expenses - savings_goal
    balance = transactions.sum
    income = income_transactions.sum
    recurring_expenses = recurring_expenses_transactions.abs_sum
    expenses = expenses_transactions.abs_sum
    savings = max(income - expected_recurring_expenses - expenses, 0)

    expected_available = expected_income - expected_recurring_expenses
    expected_remaining = max(expected_available - expenses, 0)
    expected_savings = 0
    if expected_remaining > 0:
        expected_savings = min(expected_remaining, savings_goal)
        expected_remaining -= expected_savings

    return Budget(transactions=transactions,
                  income_transactions=income_transactions,
                  recurring_expenses_transactions=recurring_expenses_transactions,
                  expenses_transactions=expenses_transactions,
                  balance=round(transactions.sum, 2),
                  income=round(income, 2),
                  recurring_expenses=round(recurring_expenses, 2),
                  expenses=round(expenses, 2),
                  savings=round(savings, 2),
                  savings_goal=round(savings_goal, 2),
                  expected_income=round(expected_income, 2),
                  expected_recurring_expenses=round(expected_recurring_expenses, 2),
                  expected_available=round(expected_available, 2),
                  expected_savings=round(expected_savings, 2),
                  expected_remaining=round(expected_remaining, 2))