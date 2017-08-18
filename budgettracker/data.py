# -*- coding: utf-8 -*-
import datetime, json, os, time, unicodecsv, re
from collections import namedtuple
from monthdelta import monthdelta


class Account(namedtuple('Account', ['id', 'title', 'amount'])):
    @classmethod
    def from_dict(cls, dct):
        return cls(**dct)

    def update(self, **kwargs):
        return Account(**dict(self._asdict(), **kwargs))

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'amount': self.amount
        }


class Transaction(namedtuple('Transaction', ['id', 'label', 'date', 'amount', 'account', 'categories', 'goal'])):
    @classmethod
    def from_dict(cls, dct):
        return cls(
            id=dct['id'],
            label=dct['label'],
            date=datetime.datetime.strptime(dct['date'], "%Y-%m-%d").date(),
            amount=float(dct['amount']),
            account=dct['account'],
            categories=dct.get('categories') or [],
            goal=dct.get('goal')
        )

    def update(self, **kwargs):
        return Transaction(**dict(self._asdict(), **kwargs))

    def to_dict(self):
        return {
            'id': self.id,
            'label': self.label,
            'date': self.date.isoformat(),
            'amount': self.amount,
            'account': self.account,
            'categories': self.categories,
            'goal': self.goal
        }

    def to_str(self, famount):
        return u"%s - %s = %s%s%s" % (self.date.isoformat(), self.label, famount(self.amount),
            ' #%s' % ', #'.join(self.categories) if self.categories else '',
            ' [%s%s]' % (famount(self.goal)) if self.goal else '')

    def __unicode__(self):
        return self.to_str()


def update_accounts(old_accounts, new_accounts):
    old = {acc.id: acc for acc in old_accounts}
    new_ids = [acc.id for acc in new_accounts]
    final = []
    for acc in new_accounts:
        if acc.id in old:
            final.append(old[acc.id].update(amount=acc.amount))
        else:
            final.append(acc)
    for acc in old_accounts:
        if acc.id not in new_ids:
            final.append(acc)
    return final


def update_transactions(old_transactions, new_transactions):
    old = {tx.id: tx for tx in old_transactions}
    final = []
    for tx in new_transactions:
        if tx.id in old:
            final.append(tx.update(
                categories=list(set(old[tx.id].categories or []) | set(tx.categories or [])),
                goal=old[tx.id].goal
            ))
        else:
            final.append(tx)
    return final


def filter_out_transactions(transactions, remove_transactions):
    return filter(lambda tx: tx not in remove_transactions, transactions)


def filter_transactions_period(transactions, start_date=None, end_date=None):
    if not start_date and not end_date:
        return transactions
    return filter(
        lambda tx: (not start_date or tx.date >= start_date) and (not end_date or tx.date < end_date),
        transactions)


def sort_transactions(transactions):
    return sorted(transactions, key=lambda tx: tx.date, reverse=True)


def split_income_expenses(transactions):
    income = filter(lambda tx: tx.amount > 0.0, transactions)
    expenses = filter(lambda tx: tx.amount <= 0.0, transactions)
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

    inter_account_transactions = []
    for id, tx in tx_out.iteritems():
        if id in tx_in:
            inter_account_transactions.append(tx)
            inter_account_transactions.append(tx_in[id])

    transactions = filter_out_transactions(transactions, inter_account_transactions)
    return inter_account_transactions, transactions


def extract_transactions_by_label(transactions, labels):
    def match_label(tx):
        for exp in labels:
            if re.match(exp, tx.label):
                return True
        return False
    matching = filter(match_label, transactions)
    transactions = filter_out_transactions(transactions, matching)
    return matching, transactions


def period_to_months(start_date, end_date):
    dates = [start_date.replace(day=1)]
    end_date = end_date.replace(day=1) - monthdelta(1)
    while dates[-1] < end_date:
        dates.append(dates[-1] + monthdelta(1))
    return dates