# -*- coding: utf-8 -*-
import datetime, json, os, time, unicodecsv, re
from collections import namedtuple


class Account(namedtuple('Account', ['id', 'title', 'amount'])):
    @classmethod
    def from_dict(cls, dct):
        return cls(**dct)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'amount': self.amount
        }


class Transaction(namedtuple('Transaction', ['id', 'label', 'date', 'amount', 'account'])):
    @classmethod
    def from_dict(cls, dct):
        return cls(
            id=dct['id'],
            label=dct['label'],
            date=datetime.date(*map(int, dct['date'].split('-'))),
            amount=dct['amount'],
            account=dct['account']
        )

    def to_dict(self):
        return {
            'id': self.id,
            'label': self.label,
            'date': self.date.isoformat(),
            'amount': self.amount,
            'account': self.account
        }

    def __unicode__(self):
        return u"%s - %s = %s€" % (self.date.isoformat(), self.label, self.amount)


def dump_accounts(accounts, filename):
    with open(filename, 'w') as f:
        json.dump(map(lambda acc: acc.to_dict(), accounts), f, indent=2)


def load_accounts(filename):
    with open(filename) as f:
        return json.load(f, object_hook=lambda dct: Account.from_dict(dct))


def dump_transactions(transactions, filename):
    with open(filename, 'w') as f:
        json.dump(map(lambda tx: tx.to_dict(), transactions), f, indent=2)


def dump_transactions_csv(transactions, filename):
    with open(filename, 'w') as f:
        writer = unicodecsv.writer(f)
        for tx in transactions:
            writer.writerow(tx)


def load_transactions(filename):
    with open(filename) as f:
        return json.load(f, object_hook=lambda dct: Transaction.from_dict(dct))


def filter_transactions(func, transactions):
    return filter(func, transactions)


def filter_out_transactions(transactions, remove_transactions):
    return filter(lambda tx: tx not in remove_transactions, transactions)


def split_income_expenses(transactions):
    income = filter(lambda tx: tx.amount > 0.0, transactions)
    expenses = filter(lambda tx: tx.amount < 0.0, transactions)
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