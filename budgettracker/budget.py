from collections import namedtuple
from .data import split_income_expenses, extract_transactions_by_label


Budget = namedtuple('Budget', ['transactions', 'income_transactions', 'recurring_expenses_transactions',
    'expenses_transactions', 'real_balance', 'balance', 'income', 'recurring_expenses', 'expenses',
    'savings',  'savings_goal', 'expected_real_balance', 'expected_balance', 'expected_income',
    'expected_recurring_expenses', 'expected_savings', 'expected_remaining'])


def budgetize(transactions, expected_income=0, expected_recurring_expenses=0, recurring_expenses_labels=None, savings_goal=0):
    income_transactions, expenses_transactions = split_income_expenses(transactions)
    recurring_expenses_transactions, expenses_transactions = extract_transactions_by_label(
        expenses_transactions, recurring_expenses_labels)

    expenses_goal = expected_income - expected_recurring_expenses - savings_goal
    real_balance = transactions.sum
    income = income_transactions.sum
    recurring_expenses = recurring_expenses_transactions.abs_sum
    expenses = expenses_transactions.abs_sum
    savings = income - expected_recurring_expenses - expenses
    balance = savings - savings_goal

    expected_real_balance = max(income, expected_income) - recurring_expenses - expenses
    expected_savings = max(income, expected_income) - expected_recurring_expenses - expenses
    expected_balance = expected_savings - savings_goal
    expected_remaining = max(expected_balance, 0)

    return Budget(transactions=transactions,
                  income_transactions=income_transactions,
                  recurring_expenses_transactions=recurring_expenses_transactions,
                  expenses_transactions=expenses_transactions,
                  real_balance=round(real_balance, 2),
                  balance=round(balance, 2),
                  income=round(income, 2),
                  recurring_expenses=round(recurring_expenses, 2),
                  expenses=round(expenses, 2),
                  savings=round(savings, 2),
                  savings_goal=round(savings_goal, 2),
                  expected_real_balance=round(expected_real_balance, 2),
                  expected_balance=round(expected_balance, 2),
                  expected_income=round(expected_income, 2),
                  expected_recurring_expenses=round(expected_recurring_expenses, 2),
                  expected_savings=round(expected_savings, 2),
                  expected_remaining=round(expected_remaining, 2))