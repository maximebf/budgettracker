
function toggleYearOverview() {
  document.querySelector('#year-overview-details').classList.toggle('open');
}

function showAllTransactions() {
  var showMore = document.querySelector('#show-more');
  if (showMore) {
    showMore.remove();
    document.querySelector('.transactions.hidden').classList.remove('hidden');
  }
}

function uploadFile() {
  document.querySelector('#update-form > input[type="file"]').click();
}

function submitUpdate(files) {
  if (files.length) {
    document.querySelector('#update-form').submit();
  }
}

function transactionNodeToObject(node) {
  var obj = {
    id: node.dataset.txId,
    date: new Date(node.dataset.txDate),
    label: node.querySelector('.label').innerText,
    amount: node.dataset.txAmount,
    amount_text: node.querySelector('.amount').innerText,
    categories: [],
    goal: null
  };
  node.querySelectorAll('.category').forEach(function(node) {
    if (node.innerText) {
      obj.categories.push(node.innerText);
    }
  });
  var goalNode = node.querySelector('.goal');
  if (goalNode) {
    obj.goal = goalNode.getAttribute('title');
  }
  return obj;
}

var selectedTransactionNode;

function showTransactionOptions(event) {
  event.stopPropagation();
  event.preventDefault();
  var form = document.querySelector('#transaction-options form');

  selectedTransactionNode = event.target.parentNode
  var tx = transactionNodeToObject(selectedTransactionNode);
  form.action = form.dataset.actionBase + '/' + (tx.date.getMonth() + 1) + '/' + tx.id;
  form.querySelector('h4').innerText = tx.label + ' (' + tx.amount_text + ')';
  form.querySelectorAll('input[name="categories"]').forEach(function(node) {
    node.checked = tx.categories.indexOf(node.value) !== -1;
  });
  form.querySelectorAll('input[name="goal"]').forEach(function(node) {
    node.checked = (!tx.goal && node.value === '') || (tx.goal && node.value === tx.goal);
  });

  document.querySelectorAll('#transaction-options label.category.new').forEach(function(node) {
    node.parentNode.removeChild(node);
  });
  document.querySelector('#transaction-options').classList.add('visible');
}

function addCategory(before) {
  var name = prompt('Name:');
  if (!name) {
    return;
  }
  var label = document.createElement('label');
  label.classList.add('category');
  label.classList.add('new');
  var check = document.createElement('input');
  check.setAttribute('type', 'checkbox');
  check.setAttribute('name', 'categories');
  check.checked = true;
  check.value = name;
  label.appendChild(check);
  label.appendChild(document.createTextNode(name));
  before.parentNode.insertBefore(label, before);
}

function onTransactionOptionsFormSubmit(event) {
  event.stopPropagation();
  event.preventDefault();
  var form = document.querySelector('#transaction-options form');

  var req = new XMLHttpRequest();
  req.responseType = 'json';
  req.addEventListener("load", function() {
    selectedTransactionNode.querySelectorAll('.category').forEach(function(node) {
      node.parentNode.removeChild(node);
    });
    var goalNode = selectedTransactionNode.querySelector('.goal');
    if (goalNode) {
      goalNode.parentNode.removeChild(goalNode);
    }
    var before = selectedTransactionNode.querySelector('.amount');
    form.querySelectorAll('input[name="goal"]').forEach(function(node) {
      if (node.checked && node.value) {
        var span = document.createElement('span');
        span.title = node.value;
        span.innerHTML = '&#9733;';
        span.classList.add('goal');
        span.onclick = showTransactionOptions;
        selectedTransactionNode.insertBefore(span, before);
      }
    });
    var hasCategory = false;
    form.querySelectorAll('input[name="categories"]').forEach(function(node) {
      if (node.checked) {
        var span = document.createElement('span');
        span.title = node.value;
        span.innerText = node.value;
        span.classList.add('category');
        span.onclick = showTransactionOptions;
        span.setAttribute("style", node.parentNode.getAttribute("style"));
        selectedTransactionNode.insertBefore(span, before);
        hasCategory = true;
      }
    });
    if (!hasCategory) {
      var span = document.createElement('span');
      span.classList.add('category');
      span.onclick = showTransactionOptions;
      selectedTransactionNode.insertBefore(span, before);
    }
    document.querySelectorAll('#transaction-options label.category.new').forEach(function(node) {
      node.classList.remove('new');
    });
    hideTransactionOptions();
  });
  req.open("POST", form.action);
  req.send(new FormData(form));
}

function hideTransactionOptions() {
  document.querySelector('#transaction-options').classList.remove('visible');
}

function filterTransactions(filter) {
  showAllTransactions();
  document.querySelectorAll('ul.transactions li').forEach(function(node) {
    var tx = transactionNodeToObject(node);
    var match = true;
    if (typeof(filter.category) !== 'undefined') {
      match = match && ((filter.category && tx.categories.indexOf(filter.category) !== -1) ||
        (!filter.category && tx.categories.length === 0));
    }
    if (typeof(filter.goal) !== 'undefined') {
      match = match && tx.goal === filter.goal;
    }
    if (match) {
      node.classList.remove('hide');
    } else {
      node.classList.add('hide');
    }
  });

  var title = document.querySelector('#filter-title');
  if (typeof(filter.category) !== 'undefined') {
    title.innerText = document.querySelector('#categories-bar > span[data-name="'
      + (filter.category || 'Uncategorized') + '"]').getAttribute('title');
  }
  if (filter.goal) {
    title.innerText = filter.goal;
  }
  title.style.display = 'block';
  document.querySelector('#clear-filter').style.display = 'block';
}

function clearTransactionsFilter() {
  document.querySelectorAll('ul.transactions li').forEach(function(node) {
    node.classList.remove('hide');
  });
  document.querySelector('#filter-title').style.display = 'none';
  document.querySelector('#clear-filter').style.display = 'none';
}

function toggleMonthSwitcher() {
  var header = document.querySelector('#header');
  var switcher = document.querySelector('#month-switcher');
  if (switcher.style.display == 'flex') {
    header.style.borderBottomWidth = '9px';
    switcher.style.display = 'none';
  } else {
    header.style.borderBottomWidth = 0;
    switcher.style.display = 'flex';
  }
}

document.addEventListener("DOMContentLoaded", function() {

  document.querySelectorAll('.tabs a').forEach(function(node) {
    node.addEventListener('click', function(e) {
      e.stopPropagation();
      e.preventDefault();
      document.querySelectorAll('.tabs li').forEach(function(n) {
        n.classList.remove('active');
      });
      document.querySelectorAll('.tab-panel').forEach(function(n) {
        n.classList.remove('active');
      });
      var id = node.getAttribute('href');
      var target = document.querySelector(id);
      if (target) {
        target.classList.add('active');
      }
      node.parentNode.classList.add('active');
    });
  });

});