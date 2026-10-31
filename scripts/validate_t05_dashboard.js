#!/usr/bin/env node
// Smoke-test dashboard render logic in Node with a small DOM stub; no browser dependency.
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

const path = process.argv[2] || 'reports/t05/dashboard_preview.html';
const html = fs.readFileSync(path, 'utf8');
const match = html.match(/const D=(.*?);\nconst n=/s);
assert(match, 'dashboard data block is present');
const data = JSON.parse(match[1]);
const script = html.match(/<script>([\s\S]*?)<\/script>/);
assert(script, 'dashboard render script is present');

const elements = {};
function element(id, width = 760) {
  return (elements[id] = {
    innerHTML: '', textContent: '', value: '',
    viewBox: { baseVal: { width } }, options: [],
    append(option) { this.options.push(option); },
    addEventListener(event, handler) { this.handlers ||= {}; this.handlers[event] = handler; },
  });
}
['kpis', 'periodNote', 'trend', 'riskTrend', 'segments', 'mix', 'context', 'scenarios'].forEach((id) => element(id));
const month = element('month');
const document = { getElementById: (id) => elements[id] || element(id), createElement: () => ({}) };
vm.runInNewContext(script[1], { document, Intl, Date, Math, Number });

assert.strictEqual(month.options.length, 57, 'all monthly snapshots are selectable');
assert(elements.kpis.innerHTML.includes('£2,493,132'), 'latest active balance KPI renders');
assert(elements.context.innerHTML.includes('21.71%'), 'latest BoE effective card rate renders');
assert(elements.scenarios.innerHTML.includes('£541,259'), 'baseline sensitivity renders');
assert(elements.mix.innerHTML.includes('90–PLUS'), 'proxy status mix renders');
month.value = '2025-09-30';
month.handlers.change();
assert(elements.context.innerHTML.includes('21.44%'), 'month selector updates context to selected month');
assert(elements.kpis.innerHTML.includes('£1,746,825'), 'month selector updates portfolio KPI to selected month');
console.log('PASS — dashboard JavaScript rendered default month, month choices, KPIs, context, scenario, and status mix');
