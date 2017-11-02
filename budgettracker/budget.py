from collections import namedtuple, OrderedDict
from .data import (split_income_expenses, extract_transactions_by_label, filter_transactions_period,
                   sort_transactions, period_to_months)
import datetime
from monthdelta import monthdelta


class Budget(namedtuple('Budget', ['month', 'transactions', 'income_transactions', 'planned_expenses_transactions',
    'expenses_transactions', 'real_balance', 'balance', 'income', 'planned_expenses', 'expenses',
    'savings',  'savings_goal', 'expected_real_balance', 'expected_balance', 'expected_income',
    'expected_planned_expenses', 'expected_savings', 'expected_remaining'])):

    @property
    def undetected_planned_expenses(self):
        return self.expected_planned_expenses - self.planned_expenses

    @property
    def all_expenses(self):
        current = datetime.date.today().replace(day=1)
        if self.month >= current:
            return self.expenses + self.expected_planned_expenses
        return self.expenses + self.planned_expenses

    @property
    def all_expected_expenses(self):
        return self.expenses + self.expected_planned_expenses

    def to_dict(self, with_transactions=True):
        dct = {
            "month": self.month,
            "real_balance": self.real_balance,
            "balance": self.balance,
            "income": self.income,
            "planned_expenses": self.planned_expenses,
            "expenses": self.expenses,
            "savings": self.savings,
            "savings_goal": self.savings_goal,
            "expected_real_balance": self.expected_real_balance,
            "expected_balance": self.expected_balance,
            "expected_income": self.expected_income,
            "expected_planned_expenses": self.expected_planned_expenses,
            "expected_savings": self.expected_savings,
            "expected_remaining": self.expected_remaining
        }
        if with_transactions:
            dct.update({
                "transactions": self.transactions,
                "income_transactions": self.income_transactions,
                "planned_expenses_transactions": self.planned_expenses_transactions,
                "expenses_transactions": self.expenses_transactions
            })
        return dct


class BudgetList(list):
    def _aggregate_transactions(self, key):
        tx = []
        for budget in self:
            tx.extend(getattr(budget, key))
        return tx

    def _sum(self, key, real=False):
        total = 0
        current = datetime.date.today().replace(day=1)
        for budget in self:
            if not real and budget.month == current and not key.startswith('expected_') and hasattr(budget, 'expected_%s' % key):
                total += getattr(budget, 'expected_%s' % key)
            elif real or budget.month < current or key.startswith('expected_'):
                total += getattr(budget, key)
        return total

    @property
    def transactions(self):
        return self._aggregate_transactions('transactions')

    @property
    def income_transactions(self):
        return self._aggregate_transactions('income_transactions')

    @property
    def planned_expenses_transactions(self):
        return self._aggregate_transactions('planned_expenses_transactions')

    @property
    def expenses_transactions(self):
        return self._aggregate_transactions('expenses_transactions')
    
    @property
    def real_balance(self):
        return self._sum('real_balance')
    
    @property
    def real_real_balance(self):
        return self._sum('real_balance', real=True)
    
    @property
    def balance(self):
        return self._sum('balance')
    
    @property
    def expected_income(self):
        return self._sum('expected_income')
    
    @property
    def income(self):
        return self._sum('income')
    
    @property
    def real_income(self):
        return self._sum('income', real=True)
    
    @property
    def expected_planned_expenses(self):
        return self._sum('expected_planned_expenses')
    
    @property
    def planned_expenses(self):
        return self._sum('planned_expenses')
    
    @property
    def real_planned_expenses(self):
        return self._sum('planned_expenses', real=True)
    
    @property
    def undetected_planned_expenses(self):
        return self._sum('undetected_planned_expenses')
    
    @property
    def expenses(self):
        return self._sum('expenses')
    
    @property
    def all_expenses(self):
        return self.expenses + self.planned_expenses
    
    @property
    def all_real_expenses(self):
        return self.expenses + self.real_planned_expenses
    
    @property
    def all_expected_expenses(self):
        return self.expenses + self.expected_planned_expenses
    
    @property
    def savings(self):
        return self._sum('savings')

    @property
    def savings_goal(self):
        return self._sum('savings_goal')

    @property
    def savings_balance(self):
        if datetime.date.today().month == 1:
            return 0
        return self.savings - self.savings_goal

    @property
    def adjusted_savings_goal(self):
        if not self.current:
            return 0
        balance = self.savings_balance
        if balance < 0:
            remaining_months = 12 - datetime.date.today().month + 1
            return self.current.savings_goal + abs(balance) / remaining_months
        return self.current.savings_goal

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


class PlannedExpense(namedtuple('PlannedExpense', ['label', 'amount', 'recurrence', 'match', 'from_date', 'to_date'])):
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
        return self.amount / self.recurrence

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


class BudgetGoal(namedtuple('BudgetGoal', ['label', 'amount'])):
    @classmethod
    def from_dict(cls, dct):
        return cls(label=dct['label'], amount=dct.get('amount'))

    @property
    def savings_per_month(self):
        if not self.amount:
            return 0
        return self.amount / 12

    def to_dict(self):
        return {
            "label": self.label,
            "amount": self.amount
        }


class ComputedBudgetGoal(namedtuple('ComputedBudgetGoal', ['label', 'target', 'saved', 'used'])):
    @classmethod
    def from_savings_goal(cls, goal, **kwargs):
        return cls(label=goal.label, target=goal.amount or 0, **kwargs)

    @property
    def completed_amount(self):
        return min(self.saved + self.used, self.target or 0)

    @property
    def completed_pct(self):
        if not self.target:
            return 0
        return round(self.completed_amount * 100 / self.target, 0)

    @property
    def remaining(self):
        if not self.target:
            return 0
        return max(self.target - self.completed_amount, 0)

    @property
    def remaining_pct(self):
        if not self.target:
            return 0
        return round(self.remaining * 100 / self.target, 0)

    @property
    def used_pct(self):
        if not self.target:
            return 0
        return round(self.used * 100 / self.target, 0)

    @property
    def saved_pct(self):
        if not self.target:
            return 0
        return round(self.saved * 100 / self.target, 0)

    @property
    def savings_per_month(self):
        if not self.target:
            return 0
        return min(self.target / 12, self.remaining)

    def to_str(self, famount):
        return "%s: %s / %s (%s%%) [used=%s saved=%s remaining=%s]" % (
            self.label, famount(self.completed_amount), famount(self.target),
            self.completed_pct, famount(self.used), famount(self.saved),
            famount(self.remaining))


def compute_budget_goals(budgets, budget_goals, debug=False):
    # TODO: reopen completed budget if we need to take from savings

    def _debug(message):
        if debug:
            print message
    _debug('STARTING COMPUTING OF GOALS')

    if not budget_goals:
        _debug('No budget goals!')
        return [], 0

    used = {g.label: 0 for g in budget_goals}
    saved = dict(used)
    remaining_goals = [g.label for g in budget_goals if g.amount]
    budget_goals = {g.label: g for g in budget_goals}
    current_month = datetime.datetime.now().replace(day=1).date()
    total_savings = 0
    savings = 0

    # for each months
    for budget in budgets:
        if budget.month > current_month:
            # only past months
            break

        savings = budget.savings if budget.month < current_month else budget.expected_savings
        _debug('%s = %s (before=%s)' % (budget.month.isoformat(), savings, total_savings))

        # computing the amount used from each goals based on the marked transactions
        for tx in budget.transactions:
            if tx.goal and tx.goal in used and tx.amount < 0:
                used[tx.goal] += abs(tx.amount)
                if budget_goals[tx.goal].amount:
                    _debug(' > Using %s from %s' % (abs(tx.amount), tx.goal))
                    if tx.goal not in remaining_goals:
                        savings += abs(tx.amount)
                        _debug(' + Goal already completed, giving %s to savings' % abs(tx.amount))

        if savings < 0 and total_savings <= 0:
            # we used money from our savings this month and there is no savings left already (...)
            total_savings += savings
            continue
        if total_savings < 0:
            # we have some savings this month, but we had a negative balance until now
            _debug(' - Using %s from new savings to pay off balance (remaining=%s)' % (abs(total_savings), total_savings + savings))
            total_savings += savings
            if total_savings < 0:
                continue
            savings = total_savings
        else:
            total_savings += savings

        # we use a while loop because if some goal completes during the loop
        # it may have some letfover savings that we will dispatch amongst other goals
        while savings != 0 and remaining_goals:
            savings_per_goal = savings / len(remaining_goals)
            savings = 0
            for goal in filter(lambda g: g.amount and g.label in remaining_goals, budget_goals.values()):
                target = goal.amount
                new_save = max(saved[goal.label] + savings_per_goal, 0)
                completed = used[goal.label] + saved[goal.label]
                new_completed = max(completed + savings_per_goal, 0)
                if new_completed >= target:
                    give_back = new_completed - target
                    savings += give_back
                    new_save = min(new_save - give_back, target)
                    _debug(' + Giving %s to %s (saved=%s, used=%s remaining=COMPLETED!, leftover=%s)' % (
                        new_save - saved[goal.label], goal.label, new_save, used[goal.label], give_back))
                    saved[goal.label] = new_save
                    remaining_goals.remove(goal.label)
                elif new_completed < completed:
                    take_back = saved[goal.label] - new_save
                    saved[goal.label] = new_save
                    _debug(' - Taking %s from %s (saved=%s, used=%s, remaining=%s)' % (
                        take_back, goal.label, new_save, used[goal.label], target - new_completed))
                else:
                    saved[goal.label] = new_save
                    _debug(' + Giving %s to %s (saved=%s, used=%s, remaining=%s)' % (
                        new_completed - completed, goal.label, new_save, used[goal.label], target - new_completed))

        if total_savings < 0:
            _debug(' ! Not enough savings to cover this month (remaining=%s)' % total_savings)
                    
        if not remaining_goals:
            break

    savings_after_goals = max(total_savings - sum(saved.values()), 0)
    _debug('END COMPUTING OF GOALS (savings=%s, after goals=%s)' % (total_savings, savings_after_goals))

    computed = []
    for goal in budget_goals.values():
        computed.append(ComputedBudgetGoal.from_savings_goal(goal,
            saved=saved[goal.label], used=used[goal.label]))
    return computed, savings_after_goals


def budgetize(transactions, start_date, end_date, *args, **kwargs):
    budgets = BudgetList()
    for date in period_to_months(start_date, end_date):
        budgets.append(budgetize_month(transactions, date, *args, **kwargs))
    return budgets


def budgetize_month(transactions, date, income_sources=None, planned_expenses=None, budget_goals=None, income_delay=0):
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
        income_sources = filter_period(income_sources, start_date, end_date)
        expected_income = sum([src.amount for src in income_sources])

    planned_expenses_transactions = []
    expected_planned_expenses = 0
    if planned_expenses:
        planned_expenses = filter_period(planned_expenses, start_date, end_date)
        planned_expenses_labels = [exp.match for exp in planned_expenses if exp.match]
        expected_planned_expenses = sum([exp.amount_per_month for exp in planned_expenses])
        planned_expenses_transactions, expenses_transactions = extract_transactions_by_label(
            expenses_transactions, planned_expenses_labels)

    savings_goal = 0
    if budget_goals:
        savings_goal = sum([s.savings_per_month for s in budget_goals])
    
    income = sum([tx.amount for tx in income_transactions])
    expenses = abs(sum([tx.amount for tx in expenses_transactions]))
    planned_expenses = abs(sum([tx.amount for tx in planned_expenses_transactions]))
    real_balance = income - planned_expenses - expenses
    savings = income - expected_planned_expenses - expenses
    balance = savings - savings_goal

    expected_real_balance = max(income, expected_income) - planned_expenses - expenses
    expected_savings = max(income, expected_income) - expected_planned_expenses - expenses
    expected_balance = expected_savings - savings_goal
    expected_remaining = max(expected_balance, 0)

    return Budget(month=start_date,
                  transactions=transactions,
                  income_transactions=income_transactions,
                  planned_expenses_transactions=planned_expenses_transactions,
                  expenses_transactions=expenses_transactions,
                  real_balance=real_balance,
                  balance=balance,
                  income=income,
                  planned_expenses=planned_expenses,
                  expenses=expenses,
                  savings=savings,
                  savings_goal=savings_goal,
                  expected_real_balance=expected_real_balance,
                  expected_balance=expected_balance,
                  expected_income=expected_income,
                  expected_planned_expenses=expected_planned_expenses,
                  expected_savings=expected_savings,
                  expected_remaining=expected_remaining)


def filter_period(objs, from_date, to_date):
    return filter(lambda obj: (not obj.from_date or obj.from_date <= from_date)\
        and (not obj.to_date or obj.to_date > from_date or obj.to_date > to_date), objs)