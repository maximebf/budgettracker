# -*- coding: utf-8 -*-
from base import *
import requests, bs4, datetime


BANKIN_URL = 'https://bankin.com'


class BankinAdapter(BankAdapter):
    name = 'Bankin'
    fetch_style = 'web'

    def login(self, session):
        r = session.get(BANKIN_URL + '/inscription?login=true')
        r.raise_for_status()
        html = bs4.BeautifulSoup(r.text, "html.parser")
        token = html.select('#login > input[name="authenticityToken"]')[0].get('value')

        r = session.post(BANKIN_URL + '/Application/authenticate', data={
            'email': self.config.get('bankin_email', ''),
            'password': self.config.get('bankin_password', ''),
            'authenticityToken': token
        })
        r.raise_for_status()
        return session

    def fetch_accounts(self):
        session = self.create_request_session()
        r = session.get(BANKIN_URL + '/Accounts/index')
        r.raise_for_status()
        html = bs4.BeautifulSoup(r.text, "html.parser")
        accounts = html.select('#contenu > .listecomptes > .scroool > p.on > span.item')
        for span in accounts:
            yield Account(id=unicode(span['nb']),
                          title=unicode(span.select('span.bankAccount')[0].string),
                          amount=float(unicode(span.select('span.bankAmount')[0].string).strip(u' €').replace(u' ', u'')))

    def fetch_transactions(self, account, start_date=None, end_date=None):
        session = self.create_request_session()
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

                transactions.append(self.make_transaction(
                    id=tx.select('.moveMonths #trId')[0]['value'],
                    label=unicode(tx.select('.nom > span.note')[0].string),
                    date=date,
                    amount=float(unicode(tx.select('p.price > span')[0].string).strip(u' €').replace(u' ', u'')),
                    account=account.id))

            fetch_from += fetch_incr

        return transactions
