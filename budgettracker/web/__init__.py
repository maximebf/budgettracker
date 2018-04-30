from flask import Flask, render_template, jsonify, request, session, redirect, url_for, abort
from werkzeug.utils import secure_filename
from monthdelta import monthdelta
from tempfile import NamedTemporaryFile
import datetime, functools, json, unicodecsv, StringIO, os, uuid, math
from ..data import sort_transactions
from ..budget import IncomeSource, PlannedExpense, BudgetGoal
from ..categories import Category, compute_categories
from ..helpers import (load_config, save_config, get_storage_from_config, get_bank_adapter_from_config,
                       load_yearly_budgets_from_config, load_monthly_budget_from_config, update_local_data,
                       compute_yearly_budget_goals_from_config, compute_monthly_categories_from_config,
                       rematch_categories, create_amount_formatter)


app = Flask(__name__)
config = load_config()
storage = get_storage_from_config(config)
bank_adapter = get_bank_adapter_from_config(config)
app.config['SECRET_KEY'] = config.get('web_passcode', 'budgettracker')
app.config['ASSETS_HASH'] = str(uuid.uuid4()).split('-')[0]
app.config.update(config.get('web_config', {}))

months_labels = list(enumerate(['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']))


def value_class(value, warning_threshold=None, zero_as_neg=False):
    if warning_threshold is not None:
        if value > 0 and value < warning_threshold:
            return 'warn'
    if zero_as_neg and value == 0:
        return 'neg'
    return 'neg' if value < 0 else 'pos'


@app.context_processor
def utility_processor():
    categories = map(Category.from_dict, config.get('categories', []))
    return dict(
        famount=create_amount_formatter(config),
        max=max,
        ceil=math.ceil,
        current_month=datetime.date.today().replace(day=1),
        value_class=value_class,
        config_categories=categories,
        category_colors={c.name: c.color for c in categories},
        config_budget_goals=map(BudgetGoal.from_dict, config.get('budget_goals', []))
    )


def requires_passcode(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if config.get('web_passcode') and not session.get('allowed') and (
          not request.authorization or request.authorization.username != config['web_passcode']):
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    return wrapper


@app.route('/login', methods=['GET', 'POST'])
def login():
    if not config.get('web_passcode'):
        return redirect(url_for('index'))
    if request.method == 'POST':
        if request.form['code'] == config.get('web_passcode'):
            session['allowed'] = True
            return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    if 'allowed' in session:
        del session['allowed']
    return redirect(url_for('index'))


@app.route('/')
@app.route('/<int:year>/<int:month>')
@requires_passcode
def index(year=None, month=None):
    current = datetime.date.today().replace(day=1)
    if year:
        date = datetime.date(year, month, 1)
    else:
        date = current

    accounts = storage.load_accounts()
    budgets = load_yearly_budgets_from_config(config, date, storage=storage)
    budget = budgets.get_from_date(date)
    categories = compute_monthly_categories_from_config(config, date, storage=storage)
    safe_to_spend = round(budget.expected_income - budget.expected_planned_expenses - budget.savings_goal, 2)

    expenses_per_day = {}
    for tx in [tx for tx in budget.transactions if tx.amount < 0 and tx not in budget.planned_expenses_transactions]:
        expenses_per_day.setdefault(tx.date.day, 0)
        expenses_per_day[tx.date.day] += abs(tx.amount)

    nb_days_in_current_month = (date.replace(day=1) + monthdelta(1) - datetime.timedelta(days=1)).day
    daily_safe_to_spend = round(safe_to_spend / nb_days_in_current_month, 2)
    chart_ideal_expenses = [daily_safe_to_spend]
    chart_expenses_per_day = [expenses_per_day.get(1, 0)]
    for i in range(2, nb_days_in_current_month + 1):
        chart_expenses_per_day.append(round(chart_expenses_per_day[i - 2] + expenses_per_day.get(i, 0), 2))
        chart_ideal_expenses.append(round(daily_safe_to_spend * i, 2))
    
    return render_template('index.html',
        date=date,
        prev_date=(date - monthdelta(1)),
        next_date=(date + monthdelta(1)) if date < current else None,
        accounts=accounts,
        account_balance=sum([a.amount for a in accounts]),
        budgets=budgets,
        budget=budget,
        chart_expenses_per_day=chart_expenses_per_day,
        chart_ideal_expenses=chart_ideal_expenses,
        chart_expenses_per_day_labels=range(1, nb_days_in_current_month + 1),
        bank_adapter=bank_adapter,
        categories=categories,
        months=months_labels)


@app.route('/<int:year>')
@requires_passcode
def year(year):
    current = datetime.date.today().replace(day=1)
    date = datetime.date(year, 1, 1)
    nb_months = 12 if date.year < current.year else current.month
    accounts = storage.load_accounts()
    budgets = load_yearly_budgets_from_config(config, date, storage=storage)

    budget_goals, savings_after_goals = compute_yearly_budget_goals_from_config(
        config, date, storage=storage)
    savings_goal = sum([g.target for g in budget_goals if g.target])
    current_savings_goal = savings_goal / 12 * nb_months

    safe_to_spend = budgets.expected_income - budgets.expected_planned_expenses - current_savings_goal
    savings = budgets.real_income - budgets.all_real_expenses
    expected_savings = budgets.income - budgets.all_expected_expenses
    if budget_goals:
        planned_savings = current_savings_goal
    else:
        planned_savings = budgets.expected_income - budgets.expected_planned_expenses

    categories = compute_categories(budgets.transactions,
        map(Category.from_dict, config.get('categories', [])),
        warning_threshold_multiplier=12)

    return render_template('year.html',
        date=date,
        prev_year=(year - 1),
        next_year=(year + 1) if year < current.year else None,
        accounts=accounts,
        account_balance=sum([a.amount for a in accounts]),
        budgets=budgets,
        budget_goals=budget_goals,
        savings_goal=savings_goal,
        savings_after_goals=savings_after_goals,
        safe_to_spend=safe_to_spend,
        savings=savings,
        expected_savings=expected_savings,
        planned_savings=planned_savings,
        categories=categories,
        months=months_labels,
        nb_months=nb_months,
        chart_months=[l for i, l in months_labels],
        chart_incomes=[round(b.income if b.month < current else b.expected_income, 2) for b in budgets],
        chart_all_expenses=[round(-b.expenses-b.expected_planned_expenses, 2) for b in budgets],
        chart_expenses=[-b.expenses for b in budgets],
        chart_savings=[round(b.savings if b.month < current else b.expected_savings, 2) for b in budgets]
    )


@app.route('/<int:year>/income')
@requires_passcode
def income(year):
    current = datetime.date.today().replace(day=1)
    date = datetime.date(year, 1, 1)
    budgets = load_yearly_budgets_from_config(config, date, storage=storage)

    chart_amounts = [0] * 12
    for budget in budgets:
        chart_amounts[budget.month.month - 1] = budget.income

    return render_template('transactions_list.html',
        page_title='Income',
        date=date,
        prev_year=(year - 1),
        next_year=(year + 1) if year < current.year else None,
        income=budgets.real_income,
        transactions=sort_transactions(budgets.income_transactions),
        chart_months=[l for i, l in months_labels],
        chart_amounts=[round(a, 2) for a in chart_amounts]
    )


@app.route('/<int:year>/planned-expenses')
@requires_passcode
def planned_expenses(year):
    current = datetime.date.today().replace(day=1)
    date = datetime.date(year, 1, 1)
    budgets = load_yearly_budgets_from_config(config, date, storage=storage)

    chart_amounts = [0] * 12
    for budget in budgets:
        chart_amounts[budget.month.month - 1] = budget.planned_expenses

    return render_template('transactions_list.html',
        page_title='Planned expenses',
        date=date,
        prev_year=(year - 1),
        next_year=(year + 1) if year < current.year else None,
        income=budgets.real_planned_expenses,
        transactions=sort_transactions(budgets.planned_expenses_transactions),
        chart_months=[l for i, l in months_labels],
        chart_amounts=[round(a, 2) for a in chart_amounts]
    )


@app.route('/<int:year>/categories/<name>')
@requires_passcode
def category(year, name):
    current = datetime.date.today().replace(day=1)
    date = datetime.date(year, 1, 1)
    name = name.lower()

    transactions = storage.load_yearly_transactions(date)
    categories = compute_categories(transactions,
        map(Category.from_dict, config.get('categories', [])),
        warning_threshold_multiplier=12)

    transactions = sort_transactions(filter(
        lambda tx: tx.amount < 0 and ((tx.categories and name in [c.lower() for c in tx.categories]) or (name == 'uncategorized' and not tx.categories)), transactions))

    chart_amounts = [0] * 12
    for tx in transactions:
        chart_amounts[tx.date.month - 1] += abs(tx.amount)

    nb_months = 12 if date.year < current.year else current.month
    monthly_average = sum(chart_amounts) / nb_months

    category = [c for c in categories if (c.name and c.name.lower() == name) or (not c.name and name == 'uncategorized')]
    if not category:
        abort(404)

    return render_template('category.html',
        date=date,
        prev_year=(year - 1),
        next_year=(year + 1) if year < current.year else None,
        transactions=transactions,
        category=category[0],
        chart_months=[l for i, l in months_labels],
        chart_amounts=[round(a, 2) for a in chart_amounts],
        chart_warning=[round(category[0].warning_threshold / 12, 2)]*12 if category[0].warning_threshold else None,
        monthly_average=monthly_average
    )


@app.route('/<int:year>/goals/<label>')
@requires_passcode
def goal(year, label):
    current = datetime.date.today().replace(day=1)
    date = datetime.date(year, 1, 1)
    label = label.lower()

    budgets = load_yearly_budgets_from_config(config, date, storage=storage)

    budget_goals, savings_after_goals = compute_yearly_budget_goals_from_config(
        config, date, storage=storage)

    goal = [g for g in budget_goals if g.label.lower() == label]
    if not goal:
        abort(404)

    transactions = sort_transactions(filter(
        lambda tx: tx.amount < 0 and tx.goal and tx.goal.lower() == label, budgets.transactions))

    chart_amounts = [0] * 12
    for tx in transactions:
        chart_amounts[tx.date.month - 1] += abs(tx.amount)

    categories = compute_categories(transactions,
        map(Category.from_dict, config.get('categories', [])),
        warning_threshold_multiplier=12)

    return render_template('goal.html',
        date=date,
        prev_year=(year - 1),
        next_year=(year + 1) if year < current.year else None,
        goal=goal[0],
        transactions=transactions,
        categories=categories,
        chart_months=[l for i, l in months_labels],
        chart_amounts=[round(a, 2) for a in chart_amounts],
    )


@app.route('/<int:year>/<int:month>/budget.json')
@requires_passcode
def budget_json(year, month):
    date = datetime.date(year, month, 1)
    budget = load_monthly_budget_from_config(config, date, storage=storage)
    return jsonify(**budget.to_dict(with_transactions=False))


@app.route('/<int:year>/<int:month>/transactions.json')
@requires_passcode
def transactions_json(year, month):
    date = datetime.date(year, month, 1)
    budget = load_monthly_budget_from_config(config, date, storage=storage)
    return jsonify(map(lambda tx: tx.to_dict(), budget.transactions))


@app.route('/<int:year>/<int:month>/transactions.csv')
@requires_passcode
def transactions_csv(year, month):
    date = datetime.date(year, month, 1)
    budget = load_monthly_budget_from_config(config, date, storage=storage)
    out = StringIO.StringIO()
    writer = unicodecsv.writer(out)
    for tx in budget.transactions:
        writer.writerow(tx)
    return out.getvalue(), {"Content-Disposition": "attachment; filename=%s-%s.csv" % (year, month),
                 "Content-Type": "text/csv"}


@app.route('/<int:year>/<int:month>/<transaction_id>', methods=['POST'])
def update_transaction(year, month, transaction_id):
    date = datetime.date(year, month, 1)
    categories = request.form.getlist('categories')
    goal = request.form.get('goal')
    storage.update_transaction(date, transaction_id, categories=categories, goal=goal)

    existing_categories = [c['name'] for c in config.get('categories') or []]
    has_new_categories = False
    for category in categories:
        if category not in existing_categories:
            if not config.get('categories'):
                config['categories'] = []
            config['categories'].append({'name': category})
            has_new_categories = True
    if has_new_categories:
        save_config(config)

    return ''


@app.route('/<int:year>/<int:month>', methods=['POST'])
@requires_passcode
def update(year, month):
    date = datetime.date(year, month, 1)
    filename = None
    delete_file = False
    if bank_adapter.fetch_type == 'file':
        if 'file' not in request.files:
            abort(400)
        file = request.files['file']
        if config.get('imports_dir'):
            filename = os.path.join(config['imports_dir'],
                '%s-%s' % (datetime.date.today().isoformat(), secure_filename(file.filename)))
            if not os.path.exists(os.path.dirname(filename)):
                os.makedirs(os.path.dirname(filename))
        else:
            temp_file = NamedTemporaryFile(delete=False)
            filename = temp_file.name
            temp_file.close()
            delete_file = True
        file.save(filename)
    update_local_data(config, date=date, filename=filename, storage=storage)
    if delete_file:
        os.unlink(filename)
    return redirect(url_for('index', year=year, month=month))


@app.route('/settings', methods=['GET', 'POST'])
@requires_passcode
def settings():
    global config
    if request.method == 'POST':
        date_cast = lambda d: datetime.datetime.strptime(d, '%Y-%m-%d').date() if d else ''
        color_cast = lambda c: '#%s' % c if not c.startswith('#') else c
        keywords_cast = lambda k: filter(bool, map(unicode.strip, k.split(',')))
        optional_float_cast = lambda f: float(f) if f else None
        income_sources = map(lambda a: IncomeSource(*a), zip(
            request.form.getlist('income_sources_label'),
            request.form.getlist('income_sources_amount', float),
            request.form.getlist('income_sources_match'),
            request.form.getlist('income_sources_from_date', date_cast),
            request.form.getlist('income_sources_to_date', date_cast)))
        planned_expenses = map(lambda a: PlannedExpense(*a), zip(
            request.form.getlist('planned_expenses_label'),
            request.form.getlist('planned_expenses_amount', float),
            request.form.getlist('planned_expenses_recurrence'),
            request.form.getlist('planned_expenses_match'),
            request.form.getlist('planned_expenses_from_date', date_cast),
            request.form.getlist('planned_expenses_to_date', date_cast)))
        budget_goals = map(lambda a: BudgetGoal(*a), zip(
            request.form.getlist('budget_goals_label'),
            request.form.getlist('budget_goals_amount', optional_float_cast)))
        categories = map(lambda a: Category(*a), zip(
            request.form.getlist('categories_name'),
            request.form.getlist('categories_color', color_cast),
            request.form.getlist('categories_keywords', keywords_cast),
            request.form.getlist('categories_warning_threshold', optional_float_cast)))

        config.update(
          income_sources=map(lambda s: s.to_dict(), income_sources),
          planned_expenses=map(lambda e: e.to_dict(), planned_expenses),
          budget_goals=map(lambda g: g.to_dict(), budget_goals),
          categories=map(lambda c: c.to_dict(), categories))

        save_config(config)
        rematch_categories(config, storage)
        return redirect(url_for('index'))

    return render_template('settings.html',
        config=config,
        income_sources=map(IncomeSource.from_dict, config.get('income_sources', [])),
        planned_expenses=map(PlannedExpense.from_dict, config.get('planned_expenses', [])),
        budget_goals=map(BudgetGoal.from_dict, config.get('budget_goals', [])),
        categories=map(Category.from_dict, config.get('categories', [])))
