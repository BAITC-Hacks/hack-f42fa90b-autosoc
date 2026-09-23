"""The local approval text uses one card and the completed request only."""

import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is optional for the Python server")
def test_approval_text_keeps_completed_request_and_verified_card_facts() -> None:
    script = r"""
const assert = require('node:assert/strict');
const { buildApprovalText, copyApprovalText } = require('./static/approval.js');
const labels = {
  city: 'City', date: 'Date', category: 'Category', eventFormat: 'Format',
  budget: 'Budget', serviceLanguage: 'Service language', hours: 'Hours', hourShort: 'h',
  approvalProfile: 'Profile: {name} ({id})', approvalConditions: 'Conditions:',
  approvalReasons: 'Reasons:', approvalReasonFormat: '{category} in {city} supports {format}.',
  approvalReasonBudget: 'Starting {price} is within {budget}.',
  approvalPrice: 'Starting {price}; confirm final quote.',
  approvalCalendar: 'Not marked busy; confirm availability.',
  approvalAvailabilityUnknown: 'Availability unknown; confirm.',
  approvalDataNotes: 'Data notes:', approvalSynthetic: 'Synthetic record.',
  approvalCityImputed: 'City imputed.', approvalPriceImputed: 'Price imputed.',
  originalCsv: 'Original CSV', extraCsv: 'Extra CSV', recordSource: 'Source: {source}',
  approvalQuestions: 'Questions:', approvalQuestionPrice: 'Final price and service scope?',
  approvalQuestionDate: 'Confirm date?', approvalQuestionDuration: 'Confirm duration?'
};
const context = {
  t: (key, data = {}) => (labels[key] || key).replace(/\{(\w+)\}/g, (_, field) => data[field] ?? ''),
  catalogLabel: (value) => value, money: (value) => `${value} KZT`, dateLabel: (value) => value,
};
const completed = Object.freeze({ city: 'Almaty', date: '2026-10-07', category: 'Host',
  event_format: 'wedding', budget_kzt: 1000000 });
const editedForm = { ...completed, date: '2026-10-10', budget_kzt: 300000 };
const card = { id: 'HK-1', anon_name: 'One profile', city: 'Almaty', categories: ['Host'],
  price_from_kzt: 400000, provenance: 'synthetic_extra', synthetic: true,
  city_imputed: true, price_imputed: true,
  facts: { date: '2026-10-07', event_format: 'wedding', budget_kzt: 1000000,
    not_marked_busy_on_date: true, max_hours: null } };
const text = buildApprovalText(card, completed, context);
assert.match(text, /One profile \(HK-1\)/);
assert.match(text, /Date: 2026-10-07/);
assert.match(text, /Budget: 1000000 KZT/);
assert.match(text, /Host in Almaty supports wedding/);
assert.match(text, /Starting 400000 KZT is within 1000000 KZT/);
assert.match(text, /Not marked busy; confirm availability/);
assert.match(text, /Synthetic record/);
assert.match(text, /City imputed/);
assert.match(text, /Price imputed/);
assert.match(text, /Confirm duration/);
assert.doesNotMatch(text, /2026-10-10|300000 KZT/);
assert.equal(editedForm.date, '2026-10-10');
const withOptional = buildApprovalText({ ...card, synthetic: false, city_imputed: false,
  price_imputed: false, facts: { ...card.facts, max_hours: 6 } },
  { ...completed, language: 'Kazakh', hours: 4 }, context);
assert.match(withOptional, /Service language: Kazakh/);
assert.match(withOptional, /Hours: 4 h/);
assert.doesNotMatch(withOptional, /Synthetic record|City imputed|Price imputed|Confirm duration/);
const uncertain = buildApprovalText({ ...card, facts: { ...card.facts, date: '2027-10-07',
  not_marked_busy_on_date: false } }, completed, context);
assert.match(uncertain, /Availability unknown/);
assert.doesNotMatch(uncertain, /Not marked busy/);
;(async () => {
assert.equal(await copyApprovalText('summary', async (value) => { assert.equal(value, 'summary'); }), true);
assert.equal(await copyApprovalText('summary', async () => { throw new Error('denied'); }), false);
assert.equal(await copyApprovalText('summary', undefined), false);
assert.equal(await copyApprovalText('summary', () => new Promise(() => {}), 5), false);
})().catch((error) => { console.error(error); process.exitCode = 1; });
"""
    result = subprocess.run(
        ["node", "-e", script], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_approval_preview_is_locally_rendered_and_clipboard_failure_stays_selectable() -> None:
    script = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    page = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    assert page.index('src="/static/approval.js"') < page.index('src="/static/app.js"')
    assert 'preview.value = window.buildApprovalText(card, snapshot' in script
    assert 'const snapshot = { ...query };' in script
    assert 'await window.copyApprovalText(preview.value, clipboardWrite)' in script
    assert 'status.textContent = t("approvalCopied")' in script
    assert 'status.textContent = t("approvalCopyFailed")' in script
    assert 'preview.select()' in script
