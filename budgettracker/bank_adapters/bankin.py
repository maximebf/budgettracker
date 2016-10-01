# -*- coding: utf-8 -*-
import requests, bs4, datetime
from budgettracker.data import Account, Transaction


BANKIN_URL = 'https://bankin.com'


def login(session, email, password):
    r = session.get(BANKIN_URL + '/inscription?login=true')
    r.raise_for_status()
    html = bs4.BeautifulSoup(r.text, "html.parser")
    token = html.select('#login > input[name="authenticityToken"]')[0].get('value')

    r = session.post(BANKIN_URL + '/Application/authenticate', data={
        'email': email,
        'password': password,
        'authenticityToken': token
    })
    r.raise_for_status()
    return session


def fetch_accounts(session):
    r = session.get(BANKIN_URL + '/Accounts/index')
    r.raise_for_status()
    html = bs4.BeautifulSoup(r.text, "html.parser")
    accounts = html.select('#contenu > .listecomptes > .scroool > p.on > span.item')
    for span in accounts:
        yield Account(id=unicode(span['nb']),
                      title=unicode(span.select('span.bankAccount')[0].string),
                      amount=float(unicode(span.select('span.bankAmount')[0].string).strip(u' €').replace(u' ', u'')))


def fetch_transactions(session, account, start_date=None, end_date=None):
    fetch_from = 0
    fetch_incr = 50
    fetch_more = True
    transactions = []
    current_year = datetime.date.today().year
    month_mapping = ['JAN', 'FEV', 'MAR', 'AVR', 'MAI', 'JUIN',
                     'JUIL', 'AOUT', 'SEPT', 'OCT', 'NOV', 'DEC']

    while fetch_more:
        r = session.post(BANKIN_URL + '/AccountsAjax/listTransactions', data={
            'accountId': account.id,
            'from': fetch_from,
            'to': fetch_from + fetch_incr
        })
        r.raise_for_status()
        html = bs4.BeautifulSoup(r.text, "html.parser")
        items = html.find_all('div', recursive=False)

        if len(items) == 1 and items[0].get('align') == 'center':
            break

        for tx in items:
            date_day = int(unicode(tx.select('p.date > span')[0].contents[0]).strip())
            date_month = unicode(tx.select('p.date > span > span')[0].contents[0]).strip().strip(u'.')
            date_month = month_mapping.index(date_month) + 1
            date_year_span = tx.select('p.date > span > span > span')
            if len(date_year_span) > 0:
                date_year = int(date_year_span[0].string)
            else:
                date_year = current_year
            date = datetime.date(date_year, date_month, date_day)

            if start_date and start_date > date:
                fetch_more = False
                break
            if end_date and end_date <= date:
                continue

            transactions.append(Transaction(
                id=tx.select('.moveMonths #trId')[0]['value'],
                label=unicode(tx.select('.nom > span.note')[0].string),
                date=date,
                amount=float(unicode(tx.select('p.price > span')[0].string).strip(u' €').replace(u' ', u'')),
                account=account.id))

        fetch_from += fetch_incr

    return transactions


def fetch_transactions_from_all_accounts(session, start_date=None, end_date=None):
    transactions = []
    for account in fetch_accounts(session):
        transactions.extend(fetch_transactions(session, account, start_date, end_date))
    return sorted(transactions, key=lambda i: i.date, reverse=True)