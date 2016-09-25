# -*- coding: utf-8 -*-
import datetime, json, os, time, unicodecsv
from collections import namedtuple


Account = namedtuple('Account', ['id', 'title', 'amount'])
Transaction = namedtuple('Transaction', ['id', 'label', 'date', 'amount', 'account'])


class TransactionList(list):
    @property
    def sum(self):
        return sum([tx.amount for tx in iter(self)])

    @property
    def abs_sum(self):
        return abs(self.sum)


def transaction_to_dict(tx):
    return {
        'id': tx.id,
        'label': tx.label,
        'date': tx.date.isoformat(),
        'amount': tx.amount,
        'account': tx.account
    }


def dump_transactions(transactions, filename):
    with open(filename, 'w') as f:
        json.dump(map(lambda tx: transaction_to_dict(tx), transactions), f, indent=2)


def dump_transactions_csv(transactions, filename):
    with open(filename, 'w') as f:
        writer = unicodecsv.writer(f)
        for tx in transactions:
            writer.writerow(tx)


def load_transactions(filename):
    with open(filename) as f:
        return TransactionList(json.load(f, object_hook=lambda dct: Transaction(
            id=dct['id'],
            label=dct['label'],
            date=datetime.date(*map(int, dct['date'].split('-'))),
            amount=dct['amount'],
            account=dct['account']
        )))


def format_transaction(transaction):
    return u"%s - %s = %s€" % (transaction.date.isoformat(), transaction.label, transaction.amount)


def account_to_dict(acc):
    return {
        'id': acc.id,
        'title': acc.title,
        'amount': acc.amount
    }


def dump_accounts(accounts, filename):
    with open(filename, 'w') as f:
        json.dump(map(lambda acc: account_to_dict(acc), accounts), f, indent=2)


def load_accounts(filename):
    with open(filename) as f:
        return json.load(f, object_hook=lambda dct: Account(**dct))