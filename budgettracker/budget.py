from collections import namedtuple
from .data import split_income_expenses, extract_transactions_by_label, filter_transactions_period, sort_transactions
import datetime
from monthdelta import monthdelta


class Budget(namedtuple('Budget', ['month', 'transactions', 'income_transactions', 'recurring_expenses_transactions',
    'expenses_transactions', 'real_balance', 'balance', 'income', 'recurring_expenses', 'expenses',
    'savings',  'savings_goal', 'expected_real_balance', 'expected_balance', 'expected_income',
    'expected_recurring_expenses', 'expected_savings', 'expected_remaining'])):

    def to_dict(self, with_transactions=True):
        dct = {
            "month": self.month,
            "real_balance": self.real_balance,
            "balance": self.balance,
            "income": self.income,
            "recurring_expenses": self.recurring_expenses,
            "expenses": self.expenses,
            "savings": self.savings,
            "savings_goal": self.savings_goal,
            "expected_real_balance": self.expected_real_balance,
            "expected_balance": self.expected_balance,
            "expected_income": self.expected_income,
            "expected_recurring_expenses": self.expected_recurring_expenses,
            "expected_savings": self.expected_savings,
            "expected_remaining": self.expected_remaining
        }
        if with_transactions:
            dct.update({
                "transactions": self.transactions,
                "income_transactions": self.income_transactions,
                "recurring_expenses_transactions": self.recurring_expenses_transactions,
                "expenses_transactions": self.expenses_transactions
            })
        return dct


class BudgetList(list):
    def _aggregate_transactions(self, key):
        tx = []
        for budget in self:
            tx.extend(getattr(budget, key))
        return tx

    def _sum(self, key):
        total = 0
        current = datetime.date.today().replace(day=1)
        for budget in self:
            if budget.month == current and not key.startswith('expected_') and hasattr(budget, 'expected_%s' % key):
                total += getattr(budget, 'expected_%s' % key)
            else:
                total += getattr(budget, key)
        return total

    @property
    def transactions(self):
        return self._aggregate_transactions('transactions')

    @property
    def income_transactions(self):
        return self._aggregate_transactions('income_transactions')

    @property
    def recurring_expenses_transactions(self):
        return self._aggregate_transactions('recurring_expenses_transactions')

    @property
    def expenses_transactions(self):
        return self._aggregate_transactions('expenses_transactions')
    
    @property
    def real_balance(self):
        return self._sum('real_balance')
    
    @property
    def balance(self):
        return self._sum('balance')
    
    @property
    def income(self):
        return self._sum('income')
    
    @property
    def recurring_expenses(self):
        return self._sum('recurring_expenses')
    
    @property
    def expenses(self):
        return self._sum('expenses')
    
    @property
    def savings(self):
        return self._sum('savings')

    @property
    def savings_goal(self):
        return self._sum('savings_goal')

    def get_from_date(self, date):
        date = date.replace(day=1)
        for budget in self:
            if budget.month == date:
                return budget

    @property
    def current(self):
        return self.get_from_date(datetime.date.today())


class IncomeSource(namedtuple('IncomeSource', ['label', 'amount', 'match', 'from_date', 'to_date'])):
    @classmethod
    def from_dict(cls, dct):
        from_date = datetime.datetime.strptime(dct['from_date'], '%Y-%m-%d').date() if dct.get('from_date') else None
        to_date = datetime.datetime.strptime(dct['to_date'], '%Y-%m-%d').date() if dct.get('to_date') else None
        return cls(label=dct['label'], amount=dct['amount'], match=dct.get('match'),
            from_date=from_date, to_date=to_date)

    def to_dict(self):
        return {
            "label": self.label,
            "amount": self.amount,
            "match": self.match,
            "from_date": self.from_date.isoformat() if self.from_date else None,
            "to_date": self.to_date.isoformat() if self.to_date else None
        }


class RecurringExpense(namedtuple('RecurringExpense', ['label', 'amount', 'recurrence', 'match', 'from_date', 'to_date'])):
    WEEKLY = 0.25
    MONTHLY = 1
    YEARLY = 12

    @classmethod
    def from_dict(cls, dct):
        recurrence = dct.get('recurrence', cls.MONTHLY)
        if isinstance(recurrence, (str, unicode)):
            recurrence = getattr(cls, recurrence.upper(), 1)
        from_date = datetime.datetime.strptime(dct['from_date'], '%Y-%m-%d').date() if dct.get('from_date') else None
        to_date = datetime.datetime.strptime(dct['to_date'], '%Y-%m-%d').date() if dct.get('to_date') else None
        return cls(label=dct['label'], amount=dct['amount'], recurrence=recurrence,
            match=dct.get('match'), from_date=from_date, to_date=to_date)

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
        return {
            "label": self.label,
            "amount": self.amount,
            "recurrence": self.recurrence_label,
            "match": self.match,
            "from_date": self.from_date.isoformat() if self.from_date else None,
            "to_date": self.to_date.isoformat() if self.to_date else None
        }


class SavingsGoal(namedtuple('SavingsGoal', ['label', 'amount'])):
    @classmethod
    def from_dict(cls, dct):
        return cls(**dct)

    def to_dict(self):
        return {
            "label": self.label,
            "amount": self.amount
        }


def period_to_months(start_date, end_date):
    dates = [start_date.replace(day=1)]
    end_date = end_date.replace(day=1) - monthdelta(1)
    while dates[-1] < end_date:
        dates.append(dates[-1] + monthdelta(1))
    return dates


def budgetize(transactions, start_date, end_date, *args, **kwargs):
    budgets = BudgetList()
    for date in period_to_months(start_date, end_date):
        budgets.append(budgetize_month(transactions, date, *args, **kwargs))
    return budgets


def _filter_period(objs, from_date, to_date):
    return filter(lambda obj: (not obj.from_date or obj.from_date < from_date)\
        and (not obj.to_date or obj.to_date >= to_date), objs)


def budgetize_month(transactions, date, income_sources=None, recurring_expenses=None, savings_goals=None, income_delay=0):
    start_date = date.replace(day=1)
    end_date = start_date + monthdelta(1)

    if income_delay:
        income_transactions, _ = split_income_expenses(filter_transactions_period(
        transactions, start_date + datetime.timedelta(days=income_delay), end_date + datetime.timedelta(days=income_delay)))
        _, expenses_transactions = split_income_expenses(filter_transactions_period(transactions, start_date, end_date))
        transactions = sort_transactions(income_transactions + expenses_transactions)
    else:
        transactions = sort_transactions(filter_transactions_period(transactions, start_date, end_date))
        income_transactions, expenses_transactions = split_income_expenses(transactions)

    expected_income = 0
    if income_sources:
        income_sources = _filter_period(income_sources, start_date, end_date)
        expected_income = sum([src.amount for src in income_sources])

    recurring_expenses_transactions = []
    expected_recurring_expenses = 0
    if recurring_expenses:
        recurring_expenses = _filter_period(recurring_expenses, start_date, end_date)
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

    return Budget(month=start_date,
                  transactions=transactions,
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