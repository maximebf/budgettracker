from collections import namedtuple
from .data import filter_transactions_period
import re


class Category(namedtuple('Category', ['name', 'color', 'keywords'])):
    @classmethod
    def from_dict(cls, dct):
        return cls(name=dct['name'], color=dct.get('color'), keywords=dct.get('keywords', []))

    def to_dict(self):
        return {
            'name': self.name,
            'color': self.color,
            'keywords': self.keywords
        }


class ComputedCategory(namedtuple('ComputedCategory', ['name', 'color', 'keywords', 'amount', 'pct'])):
    @classmethod
    def from_category(cls, category, **kwargs):
        return cls(name=category.name, color=category.color, keywords=category.keywords, **kwargs)


def compute_categories(transactions, categories=None, start_date=None, end_date=None):
    categories = {c.name: c for c in categories or []}
    amounts = {}
    total = 0
    for tx in filter_transactions_period(transactions, start_date, end_date):
        if tx.amount >= 0:
            continue
        total += abs(tx.amount)
        for name in sorted(tx.categories or []):
            amounts.setdefault(name, 0)
            amounts[name] += abs(tx.amount)
            break
    categorized_total = sum(amounts.values())
    if total - categorized_total > 0:
        amounts[None] = total - categorized_total

    final = []
    for name, amount in sorted(amounts.items(), key=lambda t: t[0]):
        pct = round(amount * 100 / total, 0)
        if name in categories:
            final.append(ComputedCategory.from_category(categories[name], amount=amount, pct=pct))
        else:
            final.append(ComputedCategory(name=name, color=None, keywords=[], amount=amount, pct=pct))
    for category in categories.values():
        if category.name not in amounts:
            final.append(ComputedCategory.from_category(category, amount=0, pct=0))

    return final


def match_categories(categories, label):
    matches = []
    for category in categories:
        for keyword in (category.keywords or []):
            if re.search(r"\b%s\b" % keyword, label, re.I):
                matches.append(category.name)
                continue
    return matches