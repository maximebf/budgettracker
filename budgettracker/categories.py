from collections import namedtuple
from .data import filter_transactions_period
import re


class Category(namedtuple('Category', ['name', 'color', 'keywords', 'warning_threshold'])):
    @classmethod
    def from_dict(cls, dct):
        return cls(name=dct['name'], color=dct.get('color'), keywords=dct.get('keywords', []),
            warning_threshold=dct.get('warning_threshold'))

    def to_dict(self):
        return {
            'name': self.name,
            'color': self.color,
            'keywords': self.keywords,
            'warning_threshold': self.warning_threshold
        }


class ComputedCategory(namedtuple('ComputedCategory', ['name', 'color', 'keywords', 'warning_threshold', 'amount', 'pct'])):
    @classmethod
    def from_category(cls, category, **kwargs):
        warning_threshold_multiplier = kwargs.pop('warning_threshold_multiplier', 1)
        warning_threshold = category.warning_threshold * warning_threshold_multiplier if category.warning_threshold else None
        return cls(name=category.name, color=category.color, keywords=category.keywords,
            warning_threshold=warning_threshold, **kwargs)

    @property
    def has_warning(self):
        return self.warning_threshold and self.amount > self.warning_threshold

    def to_str(self, famount):
        return "%s = %s (%s%%)%s" % (self.name or 'Uncategorized', famount(self.amount), self.pct,
            ' /!\ %s' % (famount(self.warning_threshold)) if self.has_warning else '')


def compute_categories(transactions, categories=None, start_date=None, end_date=None, warning_threshold_multiplier=1):
    categories = {c.name: c for c in categories or []}
    amounts = {}
    total = 0
    for tx in filter_transactions_period(transactions, start_date, end_date):
        if tx.amount >= 0:
            continue
        if not tx.categories:
            total += abs(tx.amount)
            continue
        for name in sorted(tx.categories or []):
            amounts.setdefault(name, 0)
            amounts[name] += abs(tx.amount)
            total += abs(tx.amount)
    categorized_total = sum(amounts.values())
    if total - categorized_total > 0:
        amounts[None] = total - categorized_total

    final = []
    for name, amount in sorted(amounts.items(), key=lambda t: t[0]):
        pct = round(amount * 100 / total, 0)
        if name in categories:
            final.append(ComputedCategory.from_category(categories[name], amount=amount, pct=pct,
                warning_threshold_multiplier=warning_threshold_multiplier))
        else:
            final.append(ComputedCategory(name=name, color=None, keywords=[],
                warning_threshold=None, amount=amount, pct=pct))
    for category in categories.values():
        if category.name not in amounts:
            final.append(ComputedCategory.from_category(category, amount=0, pct=0,
                warning_threshold_multiplier=warning_threshold_multiplier))
    return final


def match_categories(categories, label):
    matches = []
    for category in categories:
        for keyword in (category.keywords or []):
            if re.search(r"\b%s\b" % keyword, label, re.I):
                matches.append(category.name)
                continue
    return matches