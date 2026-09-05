const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function calculator(goal = 'raise_fc', product = 'liquid_chlorine') {
  function element(value = '') {
    return {
      value, checked: false, listeners: {},
      addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); },
      dispatch(type) { for (const fn of this.listeners[type] || []) fn(); },
    };
  }
  const fields = {
    goal: element(goal), product: element(product), strength: element('10'),
    strength_confirmed: element('true'), strength_product: element(),
  };
  const form = element();
  form.elements = fields;
  form.querySelectorAll = () => [];
  const result = { removed: false, remove() { this.removed = true; } };
  const nodes = {
    'calc-goal': fields.goal, 'calc-form': form, 'calculator-result': result,
    'strength-field': element(), 'strength-confirmation': element(),
    'strength-defaults': { textContent: JSON.stringify({
      liquid_chlorine: 10, cal_hypo: 65, muriatic_acid: 31.45,
    }) },
  };
  const window = element();
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../openpool/static/app.js'), 'utf8'), {
    document: {
      getElementById: id => nodes[id],
      querySelector: () => null, querySelectorAll: () => [],
    },
    window, navigator: {},
  });
  return { fields, form, result, nodes, window };
}

for (const [goal, product, nextField, nextValue, effective] of [
  ['raise_fc', 'liquid_chlorine', 'product', 'cal_hypo', 'cal_hypo'],
  ['raise_fc', 'cal_hypo', 'product', 'liquid_chlorine', 'liquid_chlorine'],
  ['raise_fc', 'cal_hypo', 'goal', 'slam_fc', 'liquid_chlorine'],
  ['lower_ph', 'liquid_chlorine', 'goal', 'raise_fc', 'liquid_chlorine'],
]) {
  test(`${goal}/${product} -> ${nextField}=${nextValue} clears strength and confirmation`, () => {
    const { fields, result } = calculator(goal, product);
    fields.strength_confirmed.checked = true;
    fields[nextField].value = nextValue;
    fields[nextField].dispatch('change');
    assert.equal(fields.strength.value, '');
    assert.equal(fields.strength_confirmed.checked, false);
    assert.equal(fields.strength_product.value, effective);
    assert.equal(fields.strength.required, true);
    assert.equal(result.removed, true);
    if (effective === 'cal_hypo') assert.match(fields.strength.placeholder, /65%/);
  });
}

test('editing strength invalidates confirmation; any input invalidates the old dose', () => {
  const { fields, form, result } = calculator();
  fields.strength_confirmed.checked = true;
  fields.strength.value = '12.5';
  fields.strength.dispatch('input');
  form.dispatch('input');
  assert.equal(fields.strength_confirmed.checked, false);
  assert.equal(result.removed, true);
});

test('fixed products disable unused strength fields; returning requires new confirmation', () => {
  const { fields, nodes } = calculator();
  fields.product.value = 'trichlor';
  fields.product.dispatch('change');
  assert.equal(fields.strength.disabled, true);
  assert.equal(fields.strength_confirmed.required, false);
  assert.equal(nodes['strength-field'].hidden, true);
  fields.product.value = 'cal_hypo';
  fields.product.dispatch('change');
  assert.equal(fields.strength.disabled, false);
  assert.equal(fields.strength.value, '');
  assert.equal(fields.strength_confirmed.required, true);
});

test('leaving and returning to chlorine clears strength and disables stale product outside raise FC', () => {
  const { fields } = calculator();
  fields.goal.value = 'raise_salt';
  fields.goal.dispatch('change');
  assert.equal(fields.product.disabled, true);
  assert.equal(fields.strength.disabled, true);
  fields.goal.value = 'raise_fc';
  fields.goal.dispatch('change');
  assert.equal(fields.product.disabled, false);
  assert.equal(fields.strength.disabled, false);
  assert.equal(fields.strength.value, '');
});

test('browser history restoration invalidates confirmation', () => {
  const { fields, window } = calculator();
  fields.strength_confirmed.checked = true;
  window.dispatch('pageshow');
  assert.equal(fields.strength_confirmed.checked, false);
});
