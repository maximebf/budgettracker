from collections import namedtuple
from .data import split_income_expenses, extract_transactions_by_label


Budget = namedtuple('Budget', ['transactions', 'income_transactions', 'recurring_expenses_transactions',
    'expenses_transactions', 'real_balance', 'balance', 'income', 'recurring_expenses', 'expenses',
    'savings',  'savings_goal', 'expected_real_balance', 'expected_balance', 'expected_income',
    'expected_recurring_expenses', 'expected_savings', 'expected_remaining'])


class IncomeSource(namedtuple('IncomeSource', ['label', 'amount', 'match'])):
    @classmethod
    def from_dict(cls, dct):
        return cls(label=dct['label'], amount=dct['amount'], match=dct.get('match'))

    def to_dict(self):
        return {"label": self.label,
                "amount": self.amount,
                "match": self.match}


class RecurringExpense(namedtuple('RecurringExpense', ['label', 'amount', 'recurrence', 'match'])):
    WEEKLY = 0.25
    MONTHLY = 1
    YEARLY = 12

    @classmethod
    def from_dict(cls, dct):
        recurrence = dct.get('recurrence', cls.MONTHLY)
        if isinstance(recurrence, (str, unicode)):
            recurrence = getattr(cls, recurrence.upper(), 1)
        return cls(label=dct['label'], amount=dct['amount'], recurrence=recurrence, match=dct.get('match'))

    @property
    def amount_per_month(self):
        return round(self.amount / self.recurrence, 0)

    @property
    def recurrence_label(self):
        return dict([
            (0.25, "WEEKLY"),
            (1, "MONTHLY"),
            (12, "YEARLY")
        ]).get(self.recurrence, self.recurrence)

    def to_dict(self):
        return {"label": self.label,
                "amount": self.amount,
                "recurrence": self.recurrence_label,
                "match": self.match}


class SavingsGoal(namedtuple('SavingsGoal', ['label', 'amount'])):
    @classmethod
    def from_dict(cls, dct):
        return cls(**dct)

    def to_dict(self):
        return {"label": self.label,
                "amount": self.amount}


def budgetize(transactions, income_sources=None, recurring_expenses=None, savings_goals=None):
    income_transactions, expenses_transactions = split_income_expenses(transactions)

    expected_income = 0
    if income_sources:
      expected_income = sum([src.amount for src in income_sources])

    recurring_expenses_transactions = []
    expected_recurring_expenses = 0
    if recurring_expenses:
        recurring_expenses_labels = [exp.match for exp in recurring_expenses if exp.match]
        expected_recurring_expenses = sum([exp.amount_per_month for exp in recurring_expenses])
        recurring_expenses_transactions, expenses_transactions = extract_transactions_by_label(
            expenses_transactions, recurring_expenses_labels)

    savings_goal = 0
    if savings_goals:
        savings_goal = sum([s.amount for s in savings_goals]) / 12
    
    real_balance = sum([tx.amount for tx in transactions])
    income = sum([tx.amount for tx in income_transactions])
    expenses = abs(sum([tx.amount for tx in expenses_transactions]))
    recurring_expenses = abs(sum([tx.amount for tx in recurring_expenses_transactions]))
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