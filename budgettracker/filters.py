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
    'expenses_transactions', 'balance', 'income', 'recurring_expenses', 'available', 'expenses',
    'savings', 'savings_goal', 'remaining'])


def budgetize(transactions, recurring_expenses_labels=None, savings_goal=0):
    income, expenses = split_income_expenses(transactions)
    recur_expenses, expenses = extract_transactions_by_label(expenses, recurring_expenses_labels)

    savings = 0
    remaining = max(transactions.sum, 0)
    if remaining > 0:
        savings = min(remaining, savings_goal)
        remaining -= savings

    return Budget(transactions=transactions,
                  income_transactions=income,
                  recurring_expenses_transactions=recur_expenses,
                  expenses_transactions=expenses,
                  balance=round(transactions.sum, 2),
                  income=round(income.sum, 2),
                  recurring_expenses=round(recur_expenses.abs_sum, 2),
                  available=round(income.sum - recur_expenses.abs_sum, 2),
                  expenses=round(expenses.abs_sum, 2),
                  savings=round(savings, 2),
                  savings_goal=savings_goal,
                  remaining=remaining)