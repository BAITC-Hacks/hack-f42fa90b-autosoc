"use strict";

// Pure formatter: every field comes from the selected API card and its completed request.
(function exposeApprovalSummary(root) {
  function buildApprovalText(card, query, { t, catalogLabel, money, dateLabel }) {
    const facts = card.facts || {};
    const conditions = [
      `${t("city")}: ${catalogLabel(query.city)}`,
      `${t("date")}: ${dateLabel(query.date)}`,
      `${t("category")}: ${catalogLabel(query.category)}`,
      `${t("eventFormat")}: ${catalogLabel(query.event_format)}`,
      `${t("budget")}: ${money(query.budget_kzt)}`,
    ];
    if (query.language) conditions.push(`${t("serviceLanguage")}: ${catalogLabel(query.language)}`);
    if (query.hours != null) conditions.push(`${t("hours")}: ${query.hours} ${t("hourShort")}`);

    const reasons = [];
    if (card.city === query.city && (card.categories || []).includes(query.category) &&
        facts.event_format === query.event_format) {
      reasons.push(t("approvalReasonFormat", {
        city: catalogLabel(card.city), category: catalogLabel(query.category), format: catalogLabel(query.event_format),
      }));
    }
    if (facts.budget_kzt === query.budget_kzt && Number.isInteger(card.price_from_kzt) &&
        card.price_from_kzt <= query.budget_kzt) {
      reasons.push(t("approvalReasonBudget", { price: money(card.price_from_kzt), budget: money(query.budget_kzt) }));
    }

    const notes = [];
    if (card.synthetic) notes.push(t("approvalSynthetic"));
    if (card.city_imputed) notes.push(t("approvalCityImputed"));
    if (card.price_imputed) notes.push(t("approvalPriceImputed"));
    const source = card.provenance === "original_csv" ? t("originalCsv")
      : card.provenance === "synthetic_extra" ? t("extraCsv") : String(card.provenance || "");
    if (source) notes.push(t("recordSource", { source }));

    const questions = [t("approvalQuestionPrice"), t("approvalQuestionDate")];
    if (facts.max_hours == null) questions.push(t("approvalQuestionDuration"));
    return [
      t("approvalProfile", { name: card.anon_name, id: card.id }),
      "",
      t("approvalConditions"), ...conditions,
      ...(reasons.length ? ["", t("approvalReasons"), ...reasons.slice(0, 2)] : []),
      "", t("approvalPrice", { price: money(card.price_from_kzt) }),
      facts.not_marked_busy_on_date && facts.date === query.date
        ? t("approvalCalendar") : t("approvalAvailabilityUnknown"),
      ...(notes.length ? ["", t("approvalDataNotes"), ...notes] : []),
      "", t("approvalQuestions"), ...questions.map((item) => `• ${item}`),
    ].join("\n");
  }

  async function copyApprovalText(text, writeText, timeoutMs = 2000) {
    if (typeof writeText !== "function") return false;
    let timer;
    try {
      return await Promise.race([
        Promise.resolve().then(() => writeText(text)).then(() => true, () => false),
        new Promise((resolve) => { timer = setTimeout(() => resolve(false), timeoutMs); }),
      ]);
    } catch (_error) {
      return false;
    } finally {
      clearTimeout(timer);
    }
  }

  root.buildApprovalText = buildApprovalText;
  root.copyApprovalText = copyApprovalText;
  if (typeof module !== "undefined" && module.exports) module.exports = { buildApprovalText, copyApprovalText };
})(typeof window === "undefined" ? globalThis : window);
