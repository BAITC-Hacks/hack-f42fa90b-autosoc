"use strict";

const form = document.getElementById("match-form");
const fields = {
  city: document.getElementById("city"),
  category: document.getElementById("category"),
  date: document.getElementById("date"),
  eventFormat: document.getElementById("event-format"),
  budget: document.getElementById("budget"),
  language: document.getElementById("language"),
  hours: document.getElementById("hours"),
};
const submitButton = document.getElementById("submit-button");
const submitLabel = submitButton.querySelector("span");
const demoButtons = [...document.querySelectorAll("[data-scenario]")];
const statusElement = document.getElementById("status");
const errorElement = document.getElementById("error");
const resultsElement = document.getElementById("results");
const calendarNote = document.getElementById("calendar-note");

const scenarios = {
  choice: { city: "Алматы", date: "2026-10-07", event_format: "свадьба", category: "Ведущий", budget_kzt: 1000000 },
  rare: { city: "Астана", date: "2026-09-23", event_format: "свадьба", category: "Флорист", budget_kzt: 300000 },
  empty: { city: "Алматы", date: "2026-10-10", event_format: "свадьба", category: "Ведущий", budget_kzt: 300000 },
  date: { city: "Алматы", date: "2026-10-10", event_format: "свадьба", category: "Ведущий", budget_kzt: 1000000 },
};

const reasonLabels = {
  date: "Занят на дату",
  format: "Не подходит формат",
  budget: "Выше бюджета",
  language: "Не подходит язык",
  hours: "Не подходит длительность",
  insufficient_data: "Недостаточно данных",
};
const reasonOrder = Object.keys(reasonLabels);
const fieldLabels = {
  city: "Город",
  date: "Дата",
  event_format: "Формат мероприятия",
  category: "Категория",
  budget_kzt: "Бюджет",
  language: "Язык",
  hours: "Длительность",
};
const numberFormatter = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 });
const percentFormatter = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 1 });

let optionsLoaded = false;
let activeController = null;
let requestGeneration = 0;

function element(tag, className, value) {
  const item = document.createElement(tag);
  if (className) item.className = className;
  if (value !== undefined && value !== null) item.textContent = String(value);
  return item;
}

function money(value) {
  return `${numberFormatter.format(value)} ₸`;
}

function dateLabel(isoDate) {
  return typeof isoDate === "string" && /^\d{4}-\d{2}-\d{2}$/.test(isoDate)
    ? isoDate.split("-").reverse().join(".")
    : String(isoDate ?? "");
}

function profileWord(number) {
  if (number % 10 === 1 && number % 100 !== 11) return "профиль";
  if ([2, 3, 4].includes(number % 10) && ![12, 13, 14].includes(number % 100)) return "профиля";
  return "профилей";
}

function clearError() {
  errorElement.replaceChildren();
  errorElement.hidden = true;
}

function showError(message, retry) {
  errorElement.replaceChildren(element("span", "", message));
  if (retry) {
    const retryButton = element("button", "retry-button", "Повторить загрузку");
    retryButton.type = "button";
    retryButton.addEventListener("click", retry);
    errorElement.append(" ", retryButton);
  }
  errorElement.hidden = false;
}

function setStatus(message) {
  statusElement.textContent = message;
}

function setBusy(isBusy) {
  resultsElement.setAttribute("aria-busy", String(isBusy));
  submitLabel.textContent = isBusy ? "Подбираем…" : "Подобрать подрядчиков";
}

function fillSelect(select, values, placeholder) {
  const choices = [new Option(placeholder, "")];
  for (const value of values) choices.push(new Option(value, value));
  select.replaceChildren(...choices);
}

function enableForm() {
  for (const field of Object.values(fields)) field.disabled = false;
  submitButton.disabled = false;
  for (const button of demoButtons) button.disabled = false;
}

function setScenarioValues(scenario) {
  fields.city.value = scenario.city;
  fields.category.value = scenario.category;
  fields.date.value = scenario.date;
  fields.eventFormat.value = scenario.event_format;
  fields.budget.value = String(scenario.budget_kzt);
  fields.language.value = "";
  fields.hours.value = "";
}

function showInitialState() {
  const panel = element("div", "empty-state");
  panel.append(
    element("div", "empty-symbol", "↗"),
    element("h3", "", "Начните с параметров события"),
    element("p", "", "Заполните форму или попробуйте один из проверенных сценариев. Результаты появятся здесь."),
  );
  resultsElement.replaceChildren(panel);
}

async function loadOptions() {
  clearError();
  setStatus("Загружаем варианты из каталога…");
  try {
    const response = await fetch("/api/options", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const options = await response.json();
    if (!Array.isArray(options.cities) || !Array.isArray(options.categories) ||
        !Array.isArray(options.event_formats) || !Array.isArray(options.languages) ||
        !options.calendar_start || !options.calendar_end) {
      throw new Error("Некорректный ответ сервиса");
    }
    fillSelect(fields.city, options.cities, "Выберите город");
    fillSelect(fields.category, options.categories, "Выберите категорию");
    fillSelect(fields.eventFormat, options.event_formats, "Выберите формат");
    fillSelect(fields.language, options.languages, "Любой");
    fields.date.min = options.calendar_start;
    fields.date.max = options.calendar_end;
    calendarNote.textContent = `Календарь: ${dateLabel(options.calendar_start)} — ${dateLabel(options.calendar_end)}. Вне этого периода занятость неизвестна.`;
    optionsLoaded = true;
    enableForm();
    const initial = scenarios.choice;
    if (options.cities.includes(initial.city) && options.categories.includes(initial.category) &&
        options.event_formats.includes(initial.event_format) &&
        initial.date >= options.calendar_start && initial.date <= options.calendar_end) {
      setScenarioValues(initial);
    }
    setStatus("Форма готова. Запустите подбор, чтобы увидеть результаты.");
    showInitialState();
  } catch (_error) {
    setStatus("Не удалось загрузить варианты для формы.");
    showError("Связь с сервисом не установлена. Проверьте, что приложение запущено, и повторите загрузку.", loadOptions);
  }
}

function currentPayload() {
  const payload = {
    city: fields.city.value,
    category: fields.category.value,
    date: fields.date.value,
    event_format: fields.eventFormat.value,
    budget_kzt: Number(fields.budget.value),
  };
  if (fields.language.value) payload.language = fields.language.value;
  if (fields.hours.value) payload.hours = Number(fields.hours.value);
  return payload;
}

function validationMessage(body) {
  if (!body || !Array.isArray(body.detail)) return "Проверьте введённые значения и попробуйте снова.";
  const messages = body.detail.map((item) => {
    const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : "";
    const label = fieldLabels[field] || "Параметр запроса";
    const detail = String(item.msg || "").replace(/^Value error,\s*/i, "");
    return `${label}: ${/[А-Яа-яЁё]/.test(detail) ? detail : "некорректное значение"}`;
  });
  return `Ошибка проверки: ${messages.join("; ")}`;
}

function stopPreviousRequest() {
  requestGeneration += 1;
  if (activeController) activeController.abort();
  activeController = null;
  setBusy(false);
}

function onFormEdited() {
  if (!optionsLoaded) return;
  stopPreviousRequest();
  clearError();
  resultsElement.replaceChildren();
  showInitialState();
  setStatus("Параметры изменены. Запустите подбор для нового запроса.");
}

async function requestMatch() {
  stopPreviousRequest();
  clearError();
  resultsElement.replaceChildren();
  if (!optionsLoaded) {
    showError("Варианты каталога ещё не загружены.");
    return;
  }
  if (!form.checkValidity()) {
    setStatus("Исправьте поля формы и повторите запрос.");
    showError("Проверьте обязательные поля, бюджет, длительность и дату в пределах календаря.");
    form.reportValidity();
    return;
  }

  const generation = requestGeneration;
  const controller = new AbortController();
  activeController = controller;
  setBusy(true);
  setStatus("Проверяем условия и занятость. Предыдущие результаты убраны.");

  try {
    const response = await fetch("/api/match", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(currentPayload()),
      signal: controller.signal,
    });
    const body = await response.json();
    if (generation !== requestGeneration) return;
    if (response.status === 422) {
      setStatus("Запрос отклонён проверкой данных.");
      showError(validationMessage(body));
      return;
    }
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    renderResponse(body);
    setStatus("Подбор завершён.");
  } catch (error) {
    if (generation !== requestGeneration || error.name === "AbortError") return;
    setStatus("Не удалось получить результаты.");
    showError("Ответ сервиса не получен. Проверьте соединение и повторите запрос.");
  } finally {
    if (generation === requestGeneration) {
      activeController = null;
      setBusy(false);
    }
  }
}

function fact(list, label, value) {
  const pair = element("div", "fact");
  pair.append(element("dt", "", label), element("dd", "", value));
  list.append(pair);
}

function renderCard(card, index) {
  const article = element("article", "result-card");
  const top = element("div", "card-top");
  const kicker = element("div", "card-kicker");
  kicker.append(element("span", "", `ВАРИАНТ ${String(index + 1).padStart(2, "0")}`), element("span", "", `№ ${card.id}`));
  const main = element("div", "card-main");
  const identity = element("div");
  identity.append(element("h3", "", card.anon_name), element("span", "card-location", card.city));
  const price = element("div", "card-price");
  price.append(element("small", "", "ЦЕНА ОТ"), element("span", "", money(card.price_from_kzt)));
  main.append(identity, price);
  const categories = element("div", "categories");
  for (const category of card.categories || []) categories.append(element("span", "tag", category));
  top.append(kicker, main, categories);

  const explanation = element("p", "explanation");
  explanation.append(element("span", "explanation-label", "Почему в подборке · шаблонное объяснение"),
    document.createTextNode(card.explanation || ""));

  const facts = card.facts || {};
  const factList = element("dl", "facts");
  fact(factList, "Бюджет", money(facts.budget_kzt));
  fact(factList, "Запас бюджета", `${money(facts.budget_headroom_kzt)} · ${percentFormatter.format(facts.budget_headroom_percent)}%`);
  fact(factList, "Формат", facts.event_format);
  fact(factList, "На выбранную дату", facts.not_marked_busy_on_date
    ? `Не отмечен занятым в календаре · ${dateLabel(facts.date)}`
    : `Доступность требует уточнения · ${dateLabel(facts.date)}`);
  if (facts.language) fact(factList, "Язык", `${facts.language} · указан в профиле`);
  if (facts.requested_hours != null) {
    const hoursText = facts.max_hours == null
      ? `Запрошено ${facts.requested_hours} ч · работа в каталоге не привязана к часам; длительность уточняется`
      : `Запрошено ${facts.requested_hours} ч · предел в профиле ${facts.max_hours} ч`;
    fact(factList, "Длительность", hoursText);
  }

  const provenance = element("div", "provenance");
  provenance.append(element("span", "provenance-title", "Происхождение данных"));
  const source = card.provenance === "original_csv" ? "Исходный локальный CSV"
    : card.provenance === "synthetic_extra" ? "Дополнительный локальный CSV" : String(card.provenance);
  provenance.append(
    element("span", "tag", `Запись: ${source}`),
    element("span", "tag", card.synthetic ? "Синтетический: да" : "Синтетический: нет"),
    element("span", "tag", card.city_imputed ? "Город дополнен в данных" : "Город без пометки о дополнении"),
    element("span", "tag", card.price_imputed ? "Цена дополнена в данных" : "Цена без пометки о дополнении"),
  );

  const description = element("details", "description-disclosure");
  description.append(element("summary", "", "Исходное описание профиля"),
    element("p", "", card.description || "Описание в записи отсутствует."));
  article.append(top, explanation, factList, provenance, description);
  return article;
}

function renderOutcome(response) {
  const panel = element("section", "outcome-panel");
  panel.append(element("p", "outcome-kicker", "Результат подбора"));
  let heading;
  if (response.outcome === "no_category_in_city") heading = "Категории нет в выбранном городе";
  else if (response.outcome === "all_filtered") heading = "Категория есть, но совпадений нет";
  else if (response.cards.length >= 3) heading = "Есть выбор: три варианта";
  else heading = `${response.total_matches === 1 ? "Найден" : "Найдено"} ${response.total_matches} ${profileWord(response.total_matches)}`;
  panel.append(element("h3", "", heading), element("p", "", response.message));

  const meta = element("div", "outcome-meta");
  if (response.outcome === "matched") {
    meta.append(element("span", "meta-chip", `Прошли условия: ${response.total_matches}`));
    if (response.total_matches > 3) meta.append(element("span", "meta-chip", "Показаны первые три"));
    if (response.total_matches < 3) meta.append(element("span", "meta-chip", "Меньше трёх из-за условий или числа профилей"));
  }
  if (meta.childNodes.length) panel.append(meta);

  if (response.outcome === "all_filtered") {
    const reasons = element("div", "reasons");
    for (const code of reasonOrder) {
      const count = response.primary_reason_counts?.[code] || 0;
      if (!count) continue;
      const chip = element("span", "reason-chip");
      chip.append(element("span", "", `${reasonLabels[code]}:`), element("strong", "", count));
      reasons.append(chip);
    }
    if (reasons.childNodes.length) panel.append(reasons);
  }
  return panel;
}

function renderRejected(rejected) {
  const disclosure = element("details", "rejections");
  disclosure.append(element("summary", "", `Отсеянные кандидаты · ${rejected.length}`));
  const body = element("div", "rejections-body");
  body.append(element("p", "rejections-note", "У одного профиля может быть несколько причин. Счётчики выше учитывают только основную причину каждого профиля."));
  for (const item of rejected) {
    const row = element("div", "rejected-item");
    row.append(element("p", "rejected-title", `Профиль № ${item.id}`),
      element("p", "rejected-main", `Основная причина — ${reasonLabels[item.primary_reason] || item.primary_reason}: ${item.detail}`));
    const list = element("ul");
    for (const reason of item.all_reasons || []) {
      const entry = element("li");
      entry.append(element("strong", "", `${reasonLabels[reason.code] || reason.code}: `),
        document.createTextNode(reason.detail || ""));
      list.append(entry);
    }
    row.append(list);
    body.append(row);
  }
  disclosure.append(body);
  return disclosure;
}

function renderResponse(response) {
  if (!["matched", "no_category_in_city", "all_filtered"].includes(response.outcome) ||
      !Array.isArray(response.cards) || !Array.isArray(response.rejected)) {
    throw new Error("Некорректный ответ сервиса");
  }
  const content = [renderOutcome(response)];
  for (const [index, card] of response.cards.slice(0, 3).entries()) content.push(renderCard(card, index));
  if (response.rejected.length) content.push(renderRejected(response.rejected));
  resultsElement.replaceChildren(...content);
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  requestMatch();
  if (window.matchMedia("(max-width: 760px)").matches) {
    document.querySelector(".results-column").scrollIntoView({ behavior: "smooth", block: "start" });
  }
});
form.addEventListener("input", onFormEdited);
form.addEventListener("change", onFormEdited);
for (const button of demoButtons) {
  button.addEventListener("click", () => {
    if (!optionsLoaded) return;
    setScenarioValues(scenarios[button.dataset.scenario]);
    requestMatch();
    if (window.matchMedia("(max-width: 760px)").matches) {
      document.querySelector(".results-column").scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });
}

loadOptions();
