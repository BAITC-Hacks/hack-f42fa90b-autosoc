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

const catalogLabels = {
  "Алматы": { kk: "Алматы", en: "Almaty" }, "Астана": { kk: "Астана", en: "Astana" }, "Зарубежье": { kk: "Шетелде", en: "Abroad" },
  "Банкетный зал": { kk: "Банкет залы", en: "Banquet hall" }, "Ведущий": { kk: "Жүргізуші", en: "Event host" }, "Ведущий церемонии": { kk: "Рәсім жүргізушісі", en: "Ceremony host" }, "Видеограф": { kk: "Бейнеоператор", en: "Videographer" }, "Декоратор": { kk: "Безендіруші", en: "Decorator" }, "Загородная площадка": { kk: "Қала сыртындағы алаң", en: "Countryside venue" }, "Инструменталист": { kk: "Аспапшы", en: "Instrumentalist" }, "Лайв-бэнд": { kk: "Жанды музыка тобы", en: "Live band" }, "Национальный ансамбль": { kk: "Ұлттық ансамбль", en: "National ensemble" }, "Отель": { kk: "Қонақүй", en: "Hotel" }, "Подарки и сувениры": { kk: "Сыйлықтар мен кәдесыйлар", en: "Gifts and souvenirs" }, "Ресторан": { kk: "Мейрамхана", en: "Restaurant" }, "Танцевальный коллектив": { kk: "Би тобы", en: "Dance troupe" }, "Флорист": { kk: "Флорист", en: "Florist" }, "Фото и видеобудки": { kk: "Фото және бейнебудкалар", en: "Photo and video booths" }, "Фотограф": { kk: "Фотограф", en: "Photographer" }, "Шоу-программа": { kk: "Шоу бағдарламасы", en: "Show program" },
  "день рождения": { kk: "туған күн", en: "birthday" }, "конференция": { kk: "конференция", en: "conference" }, "корпоратив": { kk: "корпоративтік іс-шара", en: "company event" }, "свадьба": { kk: "үйлену тойы", en: "wedding" }, "той": { kk: "той", en: "toi celebration" }, "юбилей": { kk: "мерейтой", en: "anniversary celebration" }, "английский": { kk: "ағылшын тілі", en: "English" }, "казахский": { kk: "қазақ тілі", en: "Kazakh" }, "русский": { kk: "орыс тілі", en: "Russian" },
};

const localeTags = { ru: "ru-RU", kk: "kk-KZ", en: "en-US" };
let locale;
try { locale = localStorage.getItem("contractor-locale"); } catch (_error) { locale = null; }
if (!["ru", "kk", "en"].includes(locale)) locale = "ru";
let numberFormatter = new Intl.NumberFormat(localeTags[locale], { maximumFractionDigits: 0 });
let percentFormatter = new Intl.NumberFormat(localeTags[locale], { maximumFractionDigits: 1 });
let optionsData = null;
let lastAgentParameters = null;
let lastNormalizations = [];
const renderedResults = new Map();
let statusState = { key: "loadingCatalog", values: {} };
let agentStatusState = { key: "agentReady", values: {} };

function t(key, values = {}) {
  const template = ui[locale]?.[key] ?? ui.ru[key] ?? key;
  return String(template).replace(/\{(\w+)\}/g, (_match, name) => String(values[name] ?? ""));
}

function catalogLabel(value) {
  return catalogLabels[String(value)]?.[locale] ?? String(value ?? "");
}

function setAgentStatus(key, values = {}) {
  agentStatusState = { key, values };
  agentStatus.textContent = t(key, values);
}

function renderStaticText() {
  document.documentElement.lang = locale;
  for (const node of document.querySelectorAll("[data-i18n]")) node.textContent = t(node.dataset.i18n);
  for (const node of document.querySelectorAll("[data-i18n-placeholder]")) node.placeholder = t(node.dataset.i18nPlaceholder);
  for (const node of document.querySelectorAll("[data-i18n-aria-label]")) node.setAttribute("aria-label", t(node.dataset.i18nAriaLabel));
  for (const button of localeButtons) {
    const active = button.dataset.locale === locale;
    button.setAttribute("aria-pressed", String(active));
    button.classList.toggle("is-active", active);
  }
}
const submitButton = document.getElementById("submit-button");
const submitLabel = submitButton.querySelector("span");
const demoButtons = [...document.querySelectorAll("[data-scenario]")];
const statusElement = document.getElementById("status");
const errorElement = document.getElementById("error");
const resultsElement = document.getElementById("results");
const calendarNote = document.getElementById("calendar-note");
const agentForm = document.getElementById("agent-form");
const agentInput = document.getElementById("agent-message");
const agentSendButton = document.getElementById("agent-send");
const agentSendLabel = document.getElementById("agent-send-label");
const agentResetButton = document.getElementById("agent-reset");
const agentHistory = document.getElementById("agent-history");
const agentStatus = document.getElementById("agent-status");
const agentError = document.getElementById("agent-error");
const agentParameters = document.getElementById("agent-parameters");
const agentResults = document.getElementById("agent-results");
const agentSource = document.getElementById("agent-source");
const agentNormalizations = document.getElementById("agent-normalizations");
const localeButtons = [...document.querySelectorAll("[data-locale]")];

const ui = {
  ru: {
    pageTitle: "Подбор подрядчиков — Событие", brandHome: "Событие — подбор подрядчиков, главная", localeGroup: "Язык интерфейса", headerNote: "Подбор по данным каталога", eyebrow: "ПОМОЩНИК ОРГАНИЗАТОРА", heroLead: "Найдите тех, кто подходит", heroAccent: "вашему событию.", heroDescription: "Укажите условия мероприятия — покажем до трёх профилей с понятными причинами выбора и проверяемыми фактами из каталога.", howItWorks: "Как работает подбор", asideFlow: "Условия → проверка занятости → подходящие варианты", asideCaption: "Без регистрации · ручная форма работает без AI",
    agentKicker: "ПОДБОР В ДИАЛОГЕ", agentTitle: "AI-помощник по подбору подрядчиков", agentIntro: "Опишите событие обычными словами. Помощник уточнит недостающее и покажет результат подбора по каталогу.", agentReset: "Новый запрос", agentHistoryLabel: "История диалога", agentExample: "Например: «Нужен ведущий в Алматы на свадьбу 7 октября 2026 года, бюджет до миллиона тенге».", agentMessageLabel: "Ваше сообщение", agentMessagePlaceholder: "Кого вы ищете, где, когда и с каким бюджетом?", agentKeyboardHint: "Enter — отправить · Shift+Enter — новая строка", send: "Отправить", sending: "Отправляем…", agentReady: "Напишите запрос или воспользуйтесь формой ниже.", recognizedParameters: "Распознанные параметры", parametersPlaceholder: "Параметры появятся после сообщения.", agentResultsPlaceholder: "Карточки появятся здесь после поиска. Проверку условий выполняет сервер.", understood: "Понял так", correction: "{input} → {field}: {canonical}",
    formTitle: "Параметры события", formSubtitle: "Расскажите, кого ищете", city: "Город", date: "Дата", category: "Категория", eventFormat: "Формат мероприятия", budget: "Бюджет, ₸", serviceLanguage: "Язык услуги", language: "Язык", durationHours: "Длительность, ч", hours: "Длительность", optional: "необязательно", loadingCities: "Загружаем города…", loadingCategories: "Загружаем категории…", loadingFormats: "Загружаем форматы…", categoryHint: "Доступны категории всего каталога, включая другие города.", priceHint: "Цена в каталоге указана «от» и не является окончательной сметой.", budgetPlaceholder: "Например, 1 000 000", hoursPlaceholder: "Например, 4", any: "Любой", selectCity: "Выберите город", selectCategory: "Выберите категорию", selectFormat: "Выберите формат", submit: "Подобрать подрядчиков", submitting: "Подбираем…", loadingCalendar: "Загружаем границы календаря…", calendarRange: "Календарь: {start} — {end}. Вне этого периода занятость неизвестна.",
    demoTitle: "Попробуйте сценарий", demoSubtitle: "Кнопка заполнит форму и выполнит запрос", demoChoice: "Плотная", demoRare: "Редкая", demoNoCategory: "Категории нет", demoEmpty: "Условия не подошли", resultsTitle: "Результаты подбора", resultsSubtitle: "До трёх карточек в порядке ответа сервиса", factsTag: "ПРОВЕРЯЕМЫЕ ФАКТЫ", loadingCatalog: "Загружаем каталог. После этого выберите условия или демонстрационный сценарий.", footerMethod: "Подбор основан на полях каталога. В диалоге AI может распознать условия; карточки и порядок формирует сервер. Фрагмент описания выбирают AI или шаблон.", footerCalendar: "Доступность проверяется только в пределах указанного календаря.",
    dateReason: "Занят на дату", formatReason: "Не подходит формат", budgetReason: "Выше бюджета", languageReason: "Не подходит язык", hoursReason: "Не подходит длительность", insufficientReason: "Недостаточно данных", profilesOne: "профиль", profilesFew: "профиля", profilesMany: "профилей", notSet: "не задано", hourShort: "ч", retryLoad: "Повторить загрузку", invalidResponse: "Некорректный ответ сервиса", invalidAgentResponse: "Некорректный ответ помощника", noMatchResult: "Нет результата подбора", invalidValue: "некорректное значение", requestParameter: "Параметр запроса", validationError: "Ошибка проверки: {details}", validationGeneric: "Проверьте введённые значения и попробуйте снова.",
    initialTitle: "Начните с параметров события", initialBody: "Заполните форму или попробуйте один из проверенных сценариев. Результаты появятся здесь.", loadingOptions: "Загружаем варианты из каталога…", ready: "Форма готова. Запустите подбор, чтобы увидеть результаты.", optionsErrorStatus: "Не удалось загрузить варианты для формы.", optionsError: "Связь с сервисом не установлена. Проверьте, что приложение запущено, и повторите загрузку.", edited: "Параметры изменены. Запустите подбор для нового запроса.", optionsPending: "Варианты каталога ещё не загружены.", fixForm: "Исправьте поля формы и повторите запрос.", formInvalid: "Проверьте обязательные поля, бюджет, длительность и дату в пределах календаря.", matching: "Проверяем условия и занятость. Предыдущие результаты убраны.", rejectedRequest: "Запрос отклонён проверкой данных.", completed: "Подбор завершён за {seconds} с.", matchErrorStatus: "Не удалось получить результаты.", matchError: "Ответ сервиса не получен. Проверьте соединение и повторите запрос.",
    option: "ВАРИАНТ {index}", number: "№ {id}", priceFrom: "ЦЕНА ОТ", whyAi: "Почему в подборке · фрагмент профиля выбран AI", whyTemplate: "Почему в подборке · шаблонное объяснение", evidence: "Источник", sourceExcerpt: "Фрагмент исходного описания: «{excerpt}»", headroom: "Запас бюджета", format: "Формат", onDate: "На выбранную дату", notBusy: "Не отмечен занятым в календаре · {date}", availabilityUnknown: "Доступность требует уточнения · {date}", languageInProfile: "{language} · указан в профиле", requestedHoursUnknown: "Запрошено {requested} ч · работа в каталоге не привязана к часам; длительность уточняется", requestedHoursLimit: "Запрошено {requested} ч · предел в профиле {limit} ч", provenance: "Происхождение данных", originalCsv: "Исходный локальный CSV", extraCsv: "Дополнительный локальный CSV", recordSource: "Запись: {source}", syntheticYes: "Синтетический: да", syntheticNo: "Синтетический: нет", cityImputedYes: "Город дополнен в данных", cityImputedNo: "Город без пометки о дополнении", priceImputedYes: "Цена дополнена в данных", priceImputedNo: "Цена без пометки о дополнении", sourceDescription: "Исходное описание профиля", noDescription: "Описание в записи отсутствует.",
    outcomeKicker: "Результат подбора", noCategory: "Категории нет в выбранном городе", allFiltered: "Категория есть, но совпадений нет", threeOptions: "Есть выбор: три варианта", found: "Найдено {count} {word}", passed: "Прошли условия: {count}", firstThree: "Показаны первые три", shortage: "Меньше трёх из-за условий или числа профилей", rejectedCandidates: "Отсеянные кандидаты · {count}", rejectedNoteAll: "У одного профиля может быть несколько причин. Счётчики выше учитывают только основную причину каждого профиля.", rejectedNote: "У одного профиля может быть несколько причин. Основная причина показана отдельно; остальные перечислены ниже.", profileNumber: "Профиль № {id}", primaryReason: "Основная причина — {reason}: {detail}",
    changedAria: "Что изменилось в подборе", changedTitle: "Что изменилось?", matchingCountChanged: "Подходящих профилей: {previous} → {current}.", dateChangeNote: "Остальные условия сохранены. Исключено по занятости: {previous} → {current}.", compareOptions: "Сравнить {count} варианта", comparisonAria: "Таблица сравнения подрядчиков, доступна горизонтальная прокрутка", comparisonCaption: "Сравнение найденных вариантов по данным каталога", condition: "Условие", feature: "Особенность из описания", featureAbsent: "Краткий фрагмент не выбран; смотрите исходное описание", descriptionAbsent: "Описание отсутствует", requestedLanguage: "Запрошенный язык", durationUnspecified: "Не привязана к часам; уточняется", durationLimit: "Предел в профиле: {hours} ч", syntheticProfile: "Синтетический профиль", nonsyntheticProfile: "Не помечен как синтетический", comparisonNote: "Цена «от» не является окончательной сметой. Особенности приведены из описаний профилей; запас бюджета не означает скидку.",
    manualFormLink: "Перейти к ручной форме ↓", user: "Вы", assistant: "Помощник", parametersNone: "Параметры пока не распознаны.", clarifyPlaceholder: "Ответьте на уточняющий вопрос, чтобы запустить подбор.", agentUnavailablePlaceholder: "Помощник сейчас не может продолжить диалог. Ручной подбор доступен ниже.", sourceUnknown: "Источник ответа неизвестен", aiUnavailable: "AI недоступен", sourceClarification: "Параметры распознал AI · вопрос сформировал сервер", sourceTemplate: "Параметры распознал AI · подбор и объяснения выполнил сервер", sourceAiExcerpts: "Параметры распознал AI · подбор выполнил сервер · фрагменты выбрал AI", sourceAiNoExcerpts: "Параметры распознал AI · подбор выполнил сервер", agentFound: "Поиск выполнен сервером по распознанным условиям. Карточки показаны в порядке API.", agentNoMatches: "Поиск выполнен сервером по распознанным условиям. Совпадений нет.", agentClarificationStatus: "Ожидаем уточнение. Уже распознанные условия сохранены.", agentUseForm: "Для подбора без AI используйте форму ниже.", messageRequired: "Введите сообщение.", agentProcessing: "Обрабатываем запрос. Прежние параметры сохранены, предыдущий результат скрыт.", agentProcessingPlaceholder: "Обрабатываем сообщение и проверяем условия…", agent422Status: "Сообщение отклонено проверкой данных. Прежние параметры сохранены.", agent422Placeholder: "После исправления сообщения попробуйте снова.", agent422Error: "Проверьте сообщение: оно должно содержать текст длиной до 700 символов.", agentErrorStatus: "Не удалось получить ответ помощника. Показаны прежние параметры.", agentTimeout: "Время ожидания истекло. Повторите сообщение или воспользуйтесь формой ниже.", agentNetworkError: "Связь с помощником не установлена. Повторите сообщение или воспользуйтесь формой ниже.", manualAvailable: "Ручной подбор доступен независимо от помощника.", resetEmpty: "Опишите событие обычными словами — помощник уточнит недостающее.", resetStatus: "Новый запрос. Контекст предыдущего диалога сброшен.",
    funnelTitle: "Как сузился выбор", funnelAll: "Во всём каталоге", funnelCity: "В городе", funnelCategory: "С категорией", funnelDate: "После даты", funnelFormat: "После формата", funnelBudget: "После бюджета", funnelLanguage: "После языка", funnelHours: "После часов", funnelData: "Полнота данных", funnelTotal: "Итог", funnelUnused: "не задан", funnelShown: "Показано до 3 из {count}", nearbyTitle: "Ближайшие подходящие даты", nearbyIntro: "На этих датах есть подходящие варианты по календарю каталога.", nearbyChoose: "Выбрать дату", nearbyCount: "{count} подходящих", nearbyNone: "В пределах двух недель подходящих дат не найдено.", localExplanation: "Профиль в {city} подходит для формата «{format}»: цена от {price} при бюджете {budget}.", outcomeNoCategoryBody: "В городе {city} нет профилей категории «{category}».", outcomeAllFilteredBody: "В городе {city} есть категория «{category}», но остальные условия исключили всех кандидатов.", outcomeMatchedBody: "Условия прошли {count} {word}. Карточки показаны в порядке подбора сервера.", originalResponse: "Подробности ответа на прежнем языке: {detail}", reasonDateDetail: "Занят на {date}", reasonFormatDetail: "Запрошенный формат «{format}» не указан в профиле", reasonBudgetDetail: "Цена «от» превышает бюджет {budget}", reasonLanguageDetail: "Запрошенный язык «{language}» не указан в профиле", reasonHoursDetail: "Запрошено {hours} ч; предел профиля меньше", reasonDataDetail: "В записи не хватает сведений для проверки условий", sourceBriefAi: "AI выбрал фрагмент", sourceBriefTemplate: "Шаблонное объяснение", sourceBriefClarification: "AI распознал условия", sourceDetailAi: "AI выбрал только фрагмент собственного описания профиля. Совпадение и порядок проверил сервер.", sourceDetailTemplate: "Объяснение составлено серверным шаблоном по фактам профиля.", originalRussian: "Оригинал на русском языке", serviceLanguageHint: "Язык интерфейса не меняет язык услуги подрядчика.",
  },
  kk: {
    pageTitle: "Мердігерлерді таңдау — Событие", brandHome: "Событие — мердігерлерді таңдау, басты бет", localeGroup: "Интерфейс тілі", headerNote: "Каталог деректері бойынша таңдау", eyebrow: "ҰЙЫМДАСТЫРУШЫҒА КӨМЕК", heroLead: "Іс-шараңызға сай", heroAccent: "мамандарды табыңыз.", heroDescription: "Іс-шара шарттарын көрсетіңіз — каталогтағы тексерілетін деректермен үшке дейін профиль ұсынамыз.", howItWorks: "Іріктеу тәртібі", asideFlow: "Шарттар → бос еместігін тексеру → сай нұсқалар", asideCaption: "Тіркеусіз · қолмен іздеу AI-сіз жұмыс істейді",
    agentKicker: "ДИАЛОГ АРҚЫЛЫ ІЗДЕУ", agentTitle: "Мердігерлерді таңдайтын AI көмекші", agentIntro: "Іс-шараңызды өз сөзіңізбен сипаттаңыз. Көмекші жетіспейтін шарттарды сұрап, каталог нәтижесін көрсетеді.", agentReset: "Жаңа сұрау", agentHistoryLabel: "Диалог тарихы", agentExample: "Мысалы: «Алматыда 2026 жылғы 7 қазандағы үйлену тойына жүргізуші керек, бюджет 1 000 000 теңге».", agentMessageLabel: "Хабарламаңыз", agentMessagePlaceholder: "Кім керек, қайда, қашан және бюджет қандай?", agentKeyboardHint: "Enter — жіберу · Shift+Enter — жаңа жол", send: "Жіберу", sending: "Жіберілуде…", agentReady: "Сұрауды жазыңыз немесе төмендегі нысанды пайдаланыңыз.", recognizedParameters: "Танылған шарттар", parametersPlaceholder: "Шарттар хабарламадан кейін пайда болады.", agentResultsPlaceholder: "Іздеуден кейін карточкалар осында шығады. Шарттарды сервер тексереді.", understood: "Осылай түсіндім", correction: "{input} → {field}: {canonical}",
    formTitle: "Іс-шара шарттары", formSubtitle: "Кім керек екенін айтыңыз", city: "Қала", date: "Күні", category: "Санат", eventFormat: "Іс-шара форматы", budget: "Бюджет, ₸", serviceLanguage: "Қызмет тілі", language: "Тіл", durationHours: "Ұзақтығы, сағ", hours: "Ұзақтығы", optional: "міндетті емес", loadingCities: "Қалалар жүктелуде…", loadingCategories: "Санаттар жүктелуде…", loadingFormats: "Форматтар жүктелуде…", categoryHint: "Басқа қалалардағы санаттар да көрсетіледі.", priceHint: "Каталогтағы «бастап» бағасы түпкілікті смета емес.", budgetPlaceholder: "Мысалы, 1 000 000", hoursPlaceholder: "Мысалы, 4", any: "Кез келген", selectCity: "Қаланы таңдаңыз", selectCategory: "Санатты таңдаңыз", selectFormat: "Форматты таңдаңыз", submit: "Мердігерлерді таңдау", submitting: "Ізделуде…", loadingCalendar: "Күнтізбе шектері жүктелуде…", calendarRange: "Күнтізбе: {start} — {end}. Бұл кезеңнен тыс бос еместігі белгісіз.",
    demoTitle: "Мысалды қолданып көріңіз", demoSubtitle: "Түйме нысанды толтырып, нақты сұрау жібереді", demoChoice: "Таңдау көп", demoRare: "Сирек санат", demoNoCategory: "Санат жоқ", demoEmpty: "Шарттар сәйкес емес", resultsTitle: "Іздеу нәтижесі", resultsSubtitle: "Сервис ретімен үшке дейін карточка", factsTag: "ТЕКСЕРІЛЕТІН ДЕРЕКТЕР", loadingCatalog: "Каталог жүктелуде. Содан кейін шарттарды не дайын мысалды таңдаңыз.", footerMethod: "Іріктеу каталог деректеріне негізделеді. AI диалогтағы шарттарды тани алады; карточкалар мен ретін сервер анықтайды. Сипаттама үзіндісін AI не үлгі таңдайды.", footerCalendar: "Бос еместігі тек көрсетілген күнтізбе ішінде тексеріледі.",
    dateReason: "Бұл күні бос емес", formatReason: "Формат сәйкес емес", budgetReason: "Бюджеттен жоғары", languageReason: "Тіл сәйкес емес", hoursReason: "Ұзақтығы сәйкес емес", insufficientReason: "Дерек жеткіліксіз", profilesOne: "профиль", profilesFew: "профиль", profilesMany: "профиль", notSet: "көрсетілмеген", hourShort: "сағ", retryLoad: "Қайта жүктеу", invalidResponse: "Сервистің жауабы қате", invalidAgentResponse: "Көмекшінің жауабы қате", noMatchResult: "Іздеу нәтижесі жоқ", invalidValue: "қате мән", requestParameter: "Сұрау шарты", validationError: "Тексеру қатесі: {details}", validationGeneric: "Енгізілген мәндерді тексеріп, қайта көріңіз.",
    initialTitle: "Іс-шара шарттарынан бастаңыз", initialBody: "Нысанды толтырыңыз немесе тексерілген мысалды таңдаңыз. Нәтиже осында көрсетіледі.", loadingOptions: "Каталог нұсқалары жүктелуде…", ready: "Нысан дайын. Нәтижені көру үшін іздеуді бастаңыз.", optionsErrorStatus: "Нысан нұсқаларын жүктеу мүмкін болмады.", optionsError: "Сервиске қосылу мүмкін болмады. Қосымша іске қосылғанын тексеріп, қайталаңыз.", edited: "Шарттар өзгерді. Жаңа іздеуді бастаңыз.", optionsPending: "Каталог нұсқалары әлі жүктелген жоқ.", fixForm: "Нысан өрістерін түзетіп, қайта көріңіз.", formInvalid: "Міндетті өрістерді, бюджетті, ұзақтықты және күнтізбедегі күнді тексеріңіз.", matching: "Шарттар мен күнтізбе тексерілуде. Алдыңғы нәтиже жасырылды.", rejectedRequest: "Сұрау деректерді тексеруден өтпеді.", completed: "Іздеу {seconds} секундта аяқталды.", matchErrorStatus: "Нәтижені алу мүмкін болмады.", matchError: "Сервер жауабы келмеді. Қосылымды тексеріп, қайталаңыз.",
    option: "НҰСҚА {index}", number: "№ {id}", priceFrom: "БАҒАСЫ БАСТАП", whyAi: "Неге ұсынылды · үзіндіні AI таңдады", whyTemplate: "Неге ұсынылды · үлгі түсіндірме", evidence: "Түпнұсқа", sourceExcerpt: "Бастапқы сипаттама үзіндісі: «{excerpt}»", headroom: "Бюджет қалдығы", format: "Формат", onDate: "Таңдалған күнде", notBusy: "Күнтізбеде бос емес деп белгіленбеген · {date}", availabilityUnknown: "Бос еместігін нақтылау қажет · {date}", languageInProfile: "{language} · профильде көрсетілген", requestedHoursUnknown: "Сұралды: {requested} сағ · каталогта сағатқа байланбаған; ұзақтығын нақтылау керек", requestedHoursLimit: "Сұралды: {requested} сағ · профильдегі шек: {limit} сағ", provenance: "Деректің шығу тегі", originalCsv: "Бастапқы жергілікті CSV", extraCsv: "Қосымша жергілікті CSV", recordSource: "Жазба: {source}", syntheticYes: "Синтетикалық: иә", syntheticNo: "Синтетикалық: жоқ", cityImputedYes: "Қала деректе толықтырылған", cityImputedNo: "Қала толықтырылмаған", priceImputedYes: "Баға деректе толықтырылған", priceImputedNo: "Баға толықтырылмаған", sourceDescription: "Профильдің бастапқы сипаттамасы", noDescription: "Жазбада сипаттама жоқ.",
    outcomeKicker: "Іздеу нәтижесі", noCategory: "Таңдалған қалада бұл санат жоқ", allFiltered: "Санат бар, бірақ сәйкес профиль жоқ", threeOptions: "Таңдау бар: үш нұсқа", found: "{count} профиль табылды", passed: "Шарттардан өтті: {count}", firstThree: "Алғашқы үшеуі көрсетілді", shortage: "Шарттарға немесе профиль санына байланысты үштен аз", rejectedCandidates: "Өтпеген кандидаттар · {count}", rejectedNoteAll: "Бір профильде бірнеше себеп болуы мүмкін. Жоғарыдағы есеп әр профильдің тек негізгі себебін санайды.", rejectedNote: "Бір профильде бірнеше себеп болуы мүмкін. Негізгі себеп бөлек, қалғандары төменде көрсетілген.", profileNumber: "Профиль № {id}", primaryReason: "Негізгі себеп — {reason}: {detail}",
    changedAria: "Іздеуде не өзгерді", changedTitle: "Не өзгерді?", matchingCountChanged: "Сәйкес профильдер: {previous} → {current}.", dateChangeNote: "Қалған шарттар сақталды. Бос еместігіне қарай шығарылды: {previous} → {current}.", compareOptions: "{count} нұсқаны салыстыру", comparisonAria: "Мердігерлерді салыстыру кестесі, көлденең жылжытуға болады", comparisonCaption: "Каталог деректері бойынша нұсқаларды салыстыру", condition: "Шарт", feature: "Сипаттамадағы ерекшелік", featureAbsent: "Қысқа үзінді таңдалмады; бастапқы сипаттаманы қараңыз", descriptionAbsent: "Сипаттама жоқ", requestedLanguage: "Сұралған тіл", durationUnspecified: "Сағатқа байланбаған; нақтылау керек", durationLimit: "Профильдегі шек: {hours} сағ", syntheticProfile: "Синтетикалық профиль", nonsyntheticProfile: "Синтетикалық деп белгіленбеген", comparisonNote: "«Бастап» бағасы түпкілікті смета емес. Ерекшеліктер профиль сипаттамасынан алынды; бюджет қалдығы жеңілдік емес.",
    manualFormLink: "Қолмен толтыратын нысанға өту ↓", user: "Сіз", assistant: "Көмекші", parametersNone: "Шарттар әлі танылған жоқ.", clarifyPlaceholder: "Іздеуді бастау үшін нақтылау сұрағына жауап беріңіз.", agentUnavailablePlaceholder: "Көмекші қазір диалогты жалғастыра алмайды. Төмендегі нысан қолжетімді.", sourceUnknown: "Жауап көзі белгісіз", aiUnavailable: "AI қолжетімсіз", sourceClarification: "Шарттарды AI таныды · сұрақты сервер құрды", sourceTemplate: "Шарттарды AI таныды · іздеу мен түсіндірмені сервер жасады", sourceAiExcerpts: "Шарттарды AI таныды · іздеуді сервер жасады · үзіндіні AI таңдады", sourceAiNoExcerpts: "Шарттарды AI таныды · іздеуді сервер жасады", agentFound: "Сервер танылған шарттармен іздеді. Карточкалар API ретімен көрсетілді.", agentNoMatches: "Сервер танылған шарттармен іздеді. Сәйкес профиль жоқ.", agentClarificationStatus: "Нақтылау күтілуде. Бұрын танылған шарттар сақталды.", agentUseForm: "AI-сіз іздеу үшін төмендегі нысанды пайдаланыңыз.", messageRequired: "Хабарлама енгізіңіз.", agentProcessing: "Сұрау өңделуде. Бұрынғы шарттар сақталды, нәтиже жасырылды.", agentProcessingPlaceholder: "Хабарлама өңделіп, шарттар тексерілуде…", agent422Status: "Хабарлама дерек тексеруінен өтпеді. Бұрынғы шарттар сақталды.", agent422Placeholder: "Хабарламаны түзетіп, қайта көріңіз.", agent422Error: "Хабарламада 700 таңбаға дейін мәтін болуы керек.", agentErrorStatus: "Көмекші жауабын алу мүмкін болмады. Бұрынғы шарттар көрсетілді.", agentTimeout: "Күту уақыты бітті. Хабарламаны қайталаңыз немесе төмендегі нысанды пайдаланыңыз.", agentNetworkError: "Көмекшімен байланыс орнатылмады. Қайталаңыз немесе төмендегі нысанды пайдаланыңыз.", manualAvailable: "Қолмен іздеу көмекшісіз де жұмыс істейді.", resetEmpty: "Іс-шараны өз сөзіңізбен сипаттаңыз — көмекші жетіспейтінін сұрайды.", resetStatus: "Жаңа сұрау. Алдыңғы диалог контексті тазартылды.",
    funnelTitle: "Таңдау қалай тарылды", funnelAll: "Бүкіл каталогта", funnelCity: "Қалада", funnelCategory: "Санатпен", funnelDate: "Күннен кейін", funnelFormat: "Форматтан кейін", funnelBudget: "Бюджеттен кейін", funnelLanguage: "Тілден кейін", funnelHours: "Сағаттан кейін", funnelData: "Деректер толықтығы", funnelTotal: "Қорытынды", funnelUnused: "көрсетілмеген", funnelShown: "{count} ішінен үшке дейін көрсетілді", nearbyTitle: "Жақын қолайлы күндер", nearbyIntro: "Бұл күндерде каталог күнтізбесі бойынша сәйкес нұсқалар бар.", nearbyChoose: "Күнді таңдау", nearbyCount: "{count} сәйкес", nearbyNone: "Екі апта ішінде қолайлы күн табылмады.", localExplanation: "{city} қаласындағы профиль «{format}» форматына сай: бағасы {price} бастап, бюджет {budget}.", outcomeNoCategoryBody: "{city} қаласында «{category}» санатындағы профиль жоқ.", outcomeAllFilteredBody: "{city} қаласында «{category}» санаты бар, бірақ қалған шарттар барлық кандидатты алып тастады.", outcomeMatchedBody: "Шарттардан {count} профиль өтті. Карточкалар сервер іріктеген ретпен көрсетілді.", originalResponse: "Алдыңғы тілдегі жауаптың егжей-тегжейі: {detail}", reasonDateDetail: "{date} күні бос емес", reasonFormatDetail: "Сұралған «{format}» форматы профильде көрсетілмеген", reasonBudgetDetail: "«Бастап» бағасы {budget} бюджетінен жоғары", reasonLanguageDetail: "Сұралған «{language}» тілі профильде көрсетілмеген", reasonHoursDetail: "{hours} сағ сұралды; профильдегі шек одан аз", reasonDataDetail: "Шарттарды тексеруге дерек жеткіліксіз", sourceBriefAi: "Үзіндіні AI таңдады", sourceBriefTemplate: "Үлгі түсіндірме", sourceBriefClarification: "AI шарттарды таныды", sourceDetailAi: "AI тек осы профильдің сипаттама үзіндісін таңдады. Сәйкестік пен ретті сервер тексерді.", sourceDetailTemplate: "Түсіндірме профиль деректері бойынша сервер үлгісімен құрылды.", originalRussian: "Орыс тіліндегі түпнұсқа", serviceLanguageHint: "Интерфейс тілі мердігердің қызмет тілін өзгертпейді.",
  },
  en: {
    pageTitle: "Find contractors — Событие", brandHome: "Событие — find contractors, home", localeGroup: "Interface language", headerNote: "Matching from catalog data", eyebrow: "EVENT PLANNING ASSISTANT", heroLead: "Find the right people for", heroAccent: "your event.", heroDescription: "Enter your event details to see up to three profiles with clear reasons and verifiable catalog facts.", howItWorks: "How matching works", asideFlow: "Requirements → calendar check → suitable options", asideCaption: "No registration · the form works without AI",
    agentKicker: "CONVERSATIONAL SEARCH", agentTitle: "AI contractor matching assistant", agentIntro: "Describe your event in your own words. The assistant will ask for missing details and show catalog matches.", agentReset: "New search", agentHistoryLabel: "Conversation history", agentExample: "For example: “I need an MC in Almaty for a wedding on 7 October 2026, budget up to 1,000,000 KZT.”", agentMessageLabel: "Your message", agentMessagePlaceholder: "Who do you need, where, when, and within what budget?", agentKeyboardHint: "Enter — send · Shift+Enter — new line", send: "Send", sending: "Sending…", agentReady: "Write a request or use the form below.", recognizedParameters: "Recognized details", parametersPlaceholder: "Details will appear after your message.", agentResultsPlaceholder: "Cards will appear here after search. The server checks the requirements.", understood: "Understood as", correction: "{input} → {field}: {canonical}",
    formTitle: "Event requirements", formSubtitle: "Tell us who you need", city: "City", date: "Date", category: "Category", eventFormat: "Event format", budget: "Budget, ₸", serviceLanguage: "Service language", language: "Language", durationHours: "Duration, h", hours: "Duration", optional: "optional", loadingCities: "Loading cities…", loadingCategories: "Loading categories…", loadingFormats: "Loading formats…", categoryHint: "Categories from the full catalog are shown, including other cities.", priceHint: "The catalog price is a starting price, not a final quote.", budgetPlaceholder: "For example, 1,000,000", hoursPlaceholder: "For example, 4", any: "Any", selectCity: "Select a city", selectCategory: "Select a category", selectFormat: "Select a format", submit: "Find contractors", submitting: "Matching…", loadingCalendar: "Loading calendar range…", calendarRange: "Calendar: {start} – {end}. Availability outside this period is unknown.",
    demoTitle: "Try a scenario", demoSubtitle: "A button fills the form and runs a real request", demoChoice: "Many options", demoRare: "Rare category", demoNoCategory: "No category in city", demoEmpty: "Requirements filter all", resultsTitle: "Matching results", resultsSubtitle: "Up to three cards in API order", factsTag: "VERIFIABLE FACTS", loadingCatalog: "Loading the catalog. Then choose requirements or a demo scenario.", footerMethod: "Matching uses catalog fields. AI may recognize conversation details; the server determines cards and order. AI or a template selects a description excerpt.", footerCalendar: "Availability is checked only within the stated calendar range.",
    dateReason: "Busy on date", formatReason: "Format mismatch", budgetReason: "Over budget", languageReason: "Language mismatch", hoursReason: "Duration mismatch", insufficientReason: "Insufficient data", profilesOne: "profile", profilesFew: "profiles", profilesMany: "profiles", notSet: "not specified", hourShort: "h", retryLoad: "Retry loading", invalidResponse: "Invalid service response", invalidAgentResponse: "Invalid assistant response", noMatchResult: "No match result", invalidValue: "invalid value", requestParameter: "Request field", validationError: "Validation error: {details}", validationGeneric: "Check your values and try again.",
    initialTitle: "Start with your event requirements", initialBody: "Complete the form or try a verified scenario. Results will appear here.", loadingOptions: "Loading catalog options…", ready: "The form is ready. Run a search to see results.", optionsErrorStatus: "Could not load form options.", optionsError: "Could not reach the service. Check that the app is running and retry.", edited: "Requirements changed. Run a new search.", optionsPending: "Catalog options have not loaded yet.", fixForm: "Correct the form fields and retry.", formInvalid: "Check required fields, budget, duration, and a date within the calendar.", matching: "Checking requirements and calendar. Previous results have been hidden.", rejectedRequest: "The request failed validation.", completed: "Matching completed in {seconds} s.", matchErrorStatus: "Could not get results.", matchError: "No response from the service. Check the connection and retry.",
    option: "OPTION {index}", number: "No. {id}", priceFrom: "STARTING PRICE", whyAi: "Why it matched · AI selected a profile excerpt", whyTemplate: "Why it matched · template explanation", evidence: "Source", sourceExcerpt: "Original description excerpt: “{excerpt}”", headroom: "Budget headroom", format: "Format", onDate: "On selected date", notBusy: "Not marked busy in the calendar · {date}", availabilityUnknown: "Availability needs confirmation · {date}", languageInProfile: "{language} · listed in profile", requestedHoursUnknown: "Requested {requested} h · catalog entry is not tied to hours; confirm duration", requestedHoursLimit: "Requested {requested} h · profile limit {limit} h", provenance: "Data provenance", originalCsv: "Original local CSV", extraCsv: "Additional local CSV", recordSource: "Record: {source}", syntheticYes: "Synthetic: yes", syntheticNo: "Synthetic: no", cityImputedYes: "City imputed in data", cityImputedNo: "City not marked as imputed", priceImputedYes: "Price imputed in data", priceImputedNo: "Price not marked as imputed", sourceDescription: "Original profile description", noDescription: "No description in this record.",
    outcomeKicker: "Match result", noCategory: "No such category in the selected city", allFiltered: "Category exists, but no profiles match", threeOptions: "Several choices: three options", found: "Found {count} {word}", passed: "Meet requirements: {count}", firstThree: "First three shown", shortage: "Fewer than three due to requirements or catalog size", rejectedCandidates: "Excluded candidates · {count}", rejectedNoteAll: "A profile can have several reasons. The counts above use only one primary reason per profile.", rejectedNote: "A profile can have several reasons. The primary reason is separate; others are listed below.", profileNumber: "Profile No. {id}", primaryReason: "Primary reason — {reason}: {detail}",
    changedAria: "What changed in matching", changedTitle: "What changed?", matchingCountChanged: "Matching profiles: {previous} → {current}.", dateChangeNote: "Other requirements stayed the same. Excluded as busy: {previous} → {current}.", compareOptions: "Compare {count} options", comparisonAria: "Contractor comparison table; horizontal scrolling available", comparisonCaption: "Compare options using catalog data", condition: "Requirement", feature: "Feature from description", featureAbsent: "No short excerpt selected; see original description", descriptionAbsent: "No description", requestedLanguage: "Requested language", durationUnspecified: "Not tied to hours; confirm", durationLimit: "Profile limit: {hours} h", syntheticProfile: "Synthetic profile", nonsyntheticProfile: "Not marked synthetic", comparisonNote: "The starting price is not a final quote. Features come from profile descriptions; budget headroom is not a discount.",
    manualFormLink: "Go to the manual form ↓", user: "You", assistant: "Assistant", parametersNone: "No details recognized yet.", clarifyPlaceholder: "Answer the clarification question to start matching.", agentUnavailablePlaceholder: "The assistant cannot continue now. The manual form is available below.", sourceUnknown: "Response source unknown", aiUnavailable: "AI unavailable", sourceClarification: "AI recognized details · server wrote the question", sourceTemplate: "AI recognized details · server matched and explained", sourceAiExcerpts: "AI recognized details · server matched · AI selected excerpts", sourceAiNoExcerpts: "AI recognized details · server matched", agentFound: "The server searched using recognized requirements. Cards are in API order.", agentNoMatches: "The server searched using recognized requirements. No matches found.", agentClarificationStatus: "Waiting for clarification. Recognized details are retained.", agentUseForm: "Use the form below to search without AI.", messageRequired: "Enter a message.", agentProcessing: "Processing request. Previous details are retained; old results are hidden.", agentProcessingPlaceholder: "Processing message and checking requirements…", agent422Status: "Message failed validation. Previous details are retained.", agent422Placeholder: "Correct the message and try again.", agent422Error: "Your message must contain text of up to 700 characters.", agentErrorStatus: "Could not get an assistant response. Previous details are shown.", agentTimeout: "Timed out. Retry the message or use the form below.", agentNetworkError: "Could not connect to the assistant. Retry or use the form below.", manualAvailable: "Manual matching works independently of the assistant.", resetEmpty: "Describe your event in your own words — the assistant will ask for missing details.", resetStatus: "New search. Previous conversation context cleared.",
    funnelTitle: "How the choices narrowed", funnelAll: "Full catalog", funnelCity: "In city", funnelCategory: "With category", funnelDate: "After date", funnelFormat: "After format", funnelBudget: "After budget", funnelLanguage: "After language", funnelHours: "After duration", funnelData: "Data completeness", funnelTotal: "Final count", funnelUnused: "not specified", funnelShown: "Up to 3 shown from {count}", nearbyTitle: "Nearby matching dates", nearbyIntro: "These dates have suitable options according to the catalog calendar.", nearbyChoose: "Choose date", nearbyCount: "{count} matching", nearbyNone: "No matching dates within two weeks.", localExplanation: "This profile in {city} supports {format}: starting price {price} within a {budget} budget.", outcomeNoCategoryBody: "There are no {category} profiles in {city}.", outcomeAllFilteredBody: "The {category} category exists in {city}, but the remaining requirements exclude every candidate.", outcomeMatchedBody: "{count} {word} meet the requirements. Cards appear in server order.", originalResponse: "Details from the earlier response language: {detail}", reasonDateDetail: "Busy on {date}", reasonFormatDetail: "Requested format {format} is not listed in this profile", reasonBudgetDetail: "Starting price exceeds the {budget} budget", reasonLanguageDetail: "Requested language {language} is not listed in this profile", reasonHoursDetail: "Requested {hours} h; profile limit is lower", reasonDataDetail: "Record lacks data needed to check requirements", sourceBriefAi: "AI selected excerpt", sourceBriefTemplate: "Template explanation", sourceBriefClarification: "AI parsed request", sourceDetailAi: "AI selected only an excerpt from this profile. The server checked matching and order.", sourceDetailTemplate: "The server composed this explanation from profile facts.", originalRussian: "Original in Russian", serviceLanguageHint: "Interface language does not change the contractor's service language.",
  },
};

const precisionUi = {
  ru: {
    filtered: "В городе и категории {candidates} кандидатов; все отсеяны ({reasons}). По занятости исключено {busy}.",
    matched: "Подходящих профилей: {count}. По занятости исключено {busy}.",
    shortage: "Карточек меньше трёх: всего {candidates} кандидатов, {rejected} не прошли условия.",
    price: "Цена от {price} превышает бюджет {budget}.",
    hours: "Запрошено {requested} ч; предел профиля {limit} ч.",
    supported: " Указаны: {values}.",
    missing: "Недостаточно данных для проверки: {values}.",
    original: "Подробности на языке предыдущего ответа: {detail}",
  },
  kk: {
    filtered: "Бұл қала мен санатта {candidates} кандидат бар; бәрі шеттетілді ({reasons}). Бос еместігіне қарай {busy} профиль алынып тасталды.",
    matched: "Сәйкес профильдер: {count}. Бос еместігіне қарай {busy} профиль алынып тасталды.",
    shortage: "Үштен аз карточка: барлығы {candidates} кандидат, {rejected} шарттардан өтпеді.",
    price: "Бағасы {price} бастап, {budget} бюджетінен жоғары.",
    hours: "{requested} сағ сұралды; профильдегі шек {limit} сағ.",
    supported: " Көрсетілгені: {values}.",
    missing: "Тексеруге дерек жеткіліксіз: {values}.",
    original: "Алдыңғы жауап тіліндегі егжей-тегжей: {detail}",
  },
  en: {
    filtered: "There are {candidates} candidates in this city and category; all were excluded ({reasons}). {busy} were marked busy.",
    matched: "Matching profiles: {count}. {busy} were excluded as busy.",
    shortage: "Fewer than three cards: {candidates} candidates in total; {rejected} failed the requirements.",
    price: "Starting price {price} exceeds the {budget} budget.",
    hours: "Requested {requested} h; profile limit {limit} h.",
    supported: " Listed: {values}.",
    missing: "Not enough data to check: {values}.",
    original: "Details in the previous response language: {detail}",
  },
};

function precise(key, values = {}) {
  return precisionUi[locale][key].replace(/\{(\w+)\}/g, (_match, name) => String(values[name] ?? ""));
}

const scenarios = {
  choice: { city: "Алматы", date: "2026-10-07", event_format: "свадьба", category: "Ведущий", budget_kzt: 1000000 },
  rare: { city: "Астана", date: "2026-09-23", event_format: "свадьба", category: "Флорист", budget_kzt: 300000 },
  noCategory: { city: "Астана", date: "2026-10-07", event_format: "свадьба", category: "Декоратор", budget_kzt: 1000000 },
  empty: { city: "Алматы", date: "2026-10-10", event_format: "свадьба", category: "Ведущий", budget_kzt: 300000 },
};

const reasonLabels = {
  date: "dateReason", format: "formatReason", budget: "budgetReason",
  language: "languageReason", hours: "hoursReason", insufficient_data: "insufficientReason",
};
const reasonOrder = Object.keys(reasonLabels);
const fieldLabels = {
  city: "city", date: "date", event_format: "eventFormat", category: "category",
  budget_kzt: "budget", language: "serviceLanguage", hours: "hours",
};

let optionsLoaded = false;
let activeController = null;
let requestGeneration = 0;
let agentSessionId = null;
let agentController = null;
let agentGeneration = 0;
const completedResults = new WeakMap();
let errorState = null;
let validationErrorBody = null;
let agentErrorState = null;
let lastAgentBody = null;
let agentResponseLocale = "ru";
let agentPlaceholderState = { key: "agentResultsPlaceholder", link: false };

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
  if (typeof isoDate !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(isoDate)) return String(isoDate ?? "");
  const date = new Date(`${isoDate}T12:00:00Z`);
  return Number.isNaN(date.getTime()) ? isoDate : new Intl.DateTimeFormat(localeTags[locale], { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "UTC" }).format(date);
}

function profileWord(number) {
  if (locale !== "ru") return t(number === 1 ? "profilesOne" : "profilesMany");
  if (number % 10 === 1 && number % 100 !== 11) return t("profilesOne");
  if ([2, 3, 4].includes(number % 10) && ![12, 13, 14].includes(number % 100)) return t("profilesFew");
  return t("profilesMany");
}

function canonicalFromLabel(label, responseLocale) {
  const trimmed = String(label).trim();
  for (const [canonical, translations] of Object.entries(catalogLabels)) {
    if (trimmed === canonical || trimmed === translations[responseLocale] || Object.values(translations).includes(trimmed)) return canonical;
  }
  return trimmed;
}

function listedValues(detail, responseLocale) {
  const part = String(detail || "").match(/:\s*([^;]+)$/)?.[1];
  if (!part) return [];
  return part.split(",").map((value) => catalogLabel(canonicalFromLabel(value, responseLocale))).filter(Boolean);
}

function detailNumbers(detail) {
  return (String(detail || "").match(/\d[\d,. ]*/g) || [])
    .map((value) => Number(value.replace(/\D/g, ""))).filter(Number.isFinite);
}

function localizedRejectionDetail(reason, query, responseLocale) {
  if (responseLocale === locale) return reason.detail || "";
  const values = listedValues(reason.detail, responseLocale);
  const numbers = detailNumbers(reason.detail);
  if (reason.code === "date") return t("reasonDateDetail", { date: dateLabel(query?.date) });
  if (reason.code === "format") return t("reasonFormatDetail", { format: catalogLabel(query?.event_format) }) +
    (values.length ? precise("supported", { values: values.join(", ") }) : "");
  if (reason.code === "budget") return numbers.length >= 2
    ? precise("price", { price: money(numbers[0]), budget: money(numbers[1]) })
    : t("reasonBudgetDetail", { budget: money(query?.budget_kzt) });
  if (reason.code === "language") return t("reasonLanguageDetail", { language: catalogLabel(query?.language) }) +
    (values.length ? precise("supported", { values: values.join(", ") }) : "");
  if (reason.code === "hours") return numbers.length >= 2
    ? precise("hours", { requested: numbers[0], limit: numbers[1] })
    : t("reasonHoursDetail", { hours: query?.hours });
  if (reason.code === "insufficient_data") {
    const source = String(reason.detail || "").toLowerCase();
    const missing = [];
    if (/формат|format/.test(source)) missing.push(`${t("eventFormat")}: ${catalogLabel(query?.event_format)}`);
    if (/цен|price|баға|бастап/.test(source)) missing.push(`${t("budget")}: ${money(query?.budget_kzt)}`);
    if (/язык|язык|language|тіл/.test(source) && query?.language) missing.push(`${t("serviceLanguage")}: ${catalogLabel(query.language)}`);
    return missing.length ? precise("missing", { values: missing.join(", ") }) : t("reasonDataDetail");
  }
  return precise("original", { detail: reason.detail });
}

function clearError() {
  errorState = null;
  validationErrorBody = null;
  errorElement.replaceChildren();
  errorElement.hidden = true;
}

function showError(key, retry = null, values = {}) {
  errorState = { key, retry, values };
  errorElement.replaceChildren(element("span", "", t(key, values)));
  if (retry) {
    const retryButton = element("button", "retry-button", t("retryLoad"));
    retryButton.type = "button";
    retryButton.addEventListener("click", retry);
    errorElement.append(" ", retryButton);
  }
  errorElement.hidden = false;
}

function setStatus(key, values = {}) {
  statusState = { key, values };
  statusElement.textContent = t(key, values);
}

function setBusy(isBusy) {
  resultsElement.setAttribute("aria-busy", String(isBusy));
  submitLabel.textContent = t(isBusy ? "submitting" : "submit");
}

function fillSelect(select, values, placeholderKey) {
  const previous = select.value;
  const choices = [new Option(t(placeholderKey), "")];
  for (const value of values) choices.push(new Option(catalogLabel(value), value));
  select.replaceChildren(...choices);
  if (values.includes(previous)) select.value = previous;
}

function renderOptions() {
  if (!optionsData) return;
  fillSelect(fields.city, optionsData.cities, "selectCity");
  fillSelect(fields.category, optionsData.categories, "selectCategory");
  fillSelect(fields.eventFormat, optionsData.event_formats, "selectFormat");
  fillSelect(fields.language, optionsData.languages, "any");
  calendarNote.textContent = t("calendarRange", { start: dateLabel(optionsData.calendar_start), end: dateLabel(optionsData.calendar_end) });
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
  fields.language.value = scenario.language || "";
  fields.hours.value = scenario.hours == null ? "" : String(scenario.hours);
}

function showInitialState() {
  const panel = element("div", "empty-state");
  panel.append(
    element("div", "empty-symbol", "↗"),
    element("h3", "", t("initialTitle")),
    element("p", "", t("initialBody")),
  );
  resultsElement.replaceChildren(panel);
}

async function loadOptions() {
  clearError();
  setStatus("loadingOptions");
  try {
    const response = await fetch("/api/options", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const options = await response.json();
    if (!Array.isArray(options.cities) || !Array.isArray(options.categories) ||
        !Array.isArray(options.event_formats) || !Array.isArray(options.languages) ||
        !options.calendar_start || !options.calendar_end) {
      throw new Error(t("invalidResponse"));
    }
    optionsData = options;
    renderOptions();
    fields.date.min = options.calendar_start;
    fields.date.max = options.calendar_end;
    optionsLoaded = true;
    enableForm();
    const initial = scenarios.choice;
    if (options.cities.includes(initial.city) && options.categories.includes(initial.category) &&
        options.event_formats.includes(initial.event_format) &&
        initial.date >= options.calendar_start && initial.date <= options.calendar_end) {
      setScenarioValues(initial);
    }
    setStatus("ready");
    showInitialState();
  } catch (_error) {
    setStatus("optionsErrorStatus");
    showError("optionsError", loadOptions);
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
  if (!body || !Array.isArray(body.detail)) return t("validationGeneric");
  const messages = body.detail.map((item) => {
    const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : "";
    const label = t(fieldLabels[field] || "requestParameter");
    return `${label}: ${t("invalidValue")}`;
  });
  return t("validationError", { details: messages.join("; ") });
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
  renderedResults.delete(resultsElement);
  setStatus("edited");
}

async function requestMatch() {
  stopPreviousRequest();
  clearError();
  resultsElement.replaceChildren();
  if (!optionsLoaded) {
    showError("optionsPending");
    return;
  }
  if (!form.checkValidity()) {
    setStatus("fixForm");
    showError("formInvalid");
    form.reportValidity();
    return;
  }

  const generation = requestGeneration;
  const controller = new AbortController();
  const payload = currentPayload();
  const requestLocale = locale;
  const startedAt = performance.now();
  activeController = controller;
  setBusy(true);
  setStatus("matching");

  try {
    const response = await fetch("/api/match", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json", "Accept-Language": requestLocale },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    const body = await response.json();
    if (generation !== requestGeneration) return;
    if (response.status === 422) {
      setStatus("rejectedRequest");
      validationErrorBody = body;
      showError(validationMessage(body));
      return;
    }
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    renderResponse(body, resultsElement, payload, requestLocale);
    const elapsed = (performance.now() - startedAt) / 1000;
    setStatus("completed", { seconds: elapsed < 0.1 ? "<0.1" : elapsed.toFixed(1) });
  } catch (error) {
    if (generation !== requestGeneration || error.name === "AbortError") return;
    setStatus("matchErrorStatus");
    showError("matchError");
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

function renderCard(card, index, responseLocale) {
  const article = element("article", "result-card");
  const top = element("div", "card-top");
  const kicker = element("div", "card-kicker");
  kicker.append(element("span", "", t("option", { index: String(index + 1).padStart(2, "0") })), element("span", "", t("number", { id: card.id })));
  const main = element("div", "card-main");
  const identity = element("div");
  identity.append(element("h3", "", card.anon_name), element("span", "card-location", catalogLabel(card.city)));
  const price = element("div", "card-price");
  price.append(element("small", "", t("priceFrom")), element("span", "", money(card.price_from_kzt)));
  main.append(identity, price);
  const categories = element("div", "categories");
  for (const category of card.categories || []) categories.append(element("span", "tag", catalogLabel(category)));
  top.append(kicker, main, categories);

  const explanation = element("div", "explanation");
  const sourceLabel = card.explanation_source === "ai_selected" ? t("sourceBriefAi") : t("sourceBriefTemplate");
  const facts = card.facts || {};
  const explanationText = responseLocale === locale ? card.explanation : t("localExplanation", {
    city: catalogLabel(card.city), format: catalogLabel(facts.event_format), price: money(card.price_from_kzt), budget: money(facts.budget_kzt),
  });
  explanation.append(
    element("span", "explanation-label", sourceLabel),
    element("p", "explanation-text", explanationText || ""),
  );
  const sourceDetails = element("details", "evidence-disclosure");
  sourceDetails.append(element("summary", "", t("evidence")),
    element("p", "", t(card.explanation_source === "ai_selected" ? "sourceDetailAi" : "sourceDetailTemplate")));
  if (typeof card.evidence_excerpt === "string" && card.evidence_excerpt.trim()) {
    sourceDetails.append(element("p", "", `${t("originalRussian")}: «${card.evidence_excerpt}»`));
  }
  explanation.append(sourceDetails);

  const factList = element("dl", "facts");
  fact(factList, t("budget"), money(facts.budget_kzt));
  fact(factList, t("headroom"), `${money(facts.budget_headroom_kzt)} · ${percentFormatter.format(facts.budget_headroom_percent)}%`);
  fact(factList, t("format"), catalogLabel(facts.event_format));
  fact(factList, t("onDate"), t(facts.not_marked_busy_on_date ? "notBusy" : "availabilityUnknown", { date: dateLabel(facts.date) }));
  if (facts.language) fact(factList, t("serviceLanguage"), t("languageInProfile", { language: catalogLabel(facts.language) }));
  if (facts.requested_hours != null) {
    const hoursText = facts.max_hours == null
      ? t("requestedHoursUnknown", { requested: facts.requested_hours })
      : t("requestedHoursLimit", { requested: facts.requested_hours, limit: facts.max_hours });
    fact(factList, t("hours"), hoursText);
  }

  const provenance = element("div", "provenance");
  provenance.append(element("span", "provenance-title", t("provenance")));
  const source = card.provenance === "original_csv" ? t("originalCsv")
    : card.provenance === "synthetic_extra" ? t("extraCsv") : String(card.provenance);
  provenance.append(
    element("span", "tag", t("recordSource", { source })),
    element("span", "tag", t(card.synthetic ? "syntheticYes" : "syntheticNo")),
    element("span", "tag", t(card.city_imputed ? "cityImputedYes" : "cityImputedNo")),
    element("span", "tag", t(card.price_imputed ? "priceImputedYes" : "priceImputedNo")),
  );

  const description = element("details", "description-disclosure");
  description.append(element("summary", "", `${t("sourceDescription")} · ${t("originalRussian")}`),
    element("p", "", card.description || t("noDescription")));
  article.append(top, explanation, factList, provenance, description);
  return article;
}

function renderOutcome(response, query, responseLocale) {
  const panel = element("section", "outcome-panel");
  panel.append(element("p", "outcome-kicker", t("outcomeKicker")));
  let heading;
  if (response.outcome === "no_category_in_city") heading = t("noCategory");
  else if (response.outcome === "all_filtered") heading = t("allFiltered");
  else if (response.cards.length >= 3) heading = t("threeOptions");
  else heading = t("found", { count: response.total_matches, word: profileWord(response.total_matches) });
  let body = response.message;
  if (responseLocale !== locale) {
    const values = { city: catalogLabel(query?.city), category: catalogLabel(query?.category), count: response.total_matches, word: profileWord(response.total_matches) };
    if (response.outcome === "no_category_in_city") body = t("outcomeNoCategoryBody", values);
    else if (response.outcome === "all_filtered") {
      const reasons = reasonOrder.filter((code) => response.primary_reason_counts?.[code])
        .map((code) => `${t(reasonLabels[code])}: ${response.primary_reason_counts[code]}`).join(", ");
      body = precise("filtered", { candidates: response.rejected.length, reasons, busy: response.excluded_by_date });
    } else {
      body = precise("matched", { count: response.total_matches, busy: response.excluded_by_date });
      if (response.total_matches < 3) body += ` ${precise("shortage", {
        candidates: response.total_matches + response.rejected.length, rejected: response.rejected.length,
      })}`;
    }
  }
  panel.append(element("h3", "", heading), element("p", "", body));

  const meta = element("div", "outcome-meta");
  if (response.outcome === "matched") {
    meta.append(element("span", "meta-chip", t("passed", { count: response.total_matches })));
    if (response.total_matches > 3) meta.append(element("span", "meta-chip", t("firstThree")));
    if (response.total_matches < 3) meta.append(element("span", "meta-chip", t("shortage")));
  }
  if (meta.childNodes.length) panel.append(meta);

  if (response.outcome === "all_filtered" || (response.outcome === "matched" && response.total_matches < 3)) {
    const reasons = element("div", "reasons");
    for (const code of reasonOrder) {
      const count = response.primary_reason_counts?.[code] || 0;
      if (!count) continue;
      const chip = element("span", "reason-chip");
      chip.append(element("span", "", `${t(reasonLabels[code])}:`), element("strong", "", count));
      reasons.append(chip);
    }
    if (reasons.childNodes.length) panel.append(reasons);
  }
  return panel;
}

function renderRejected(rejected, outcome, responseLocale, query) {
  const disclosure = element("details", "rejections");
  disclosure.append(element("summary", "", t("rejectedCandidates", { count: rejected.length })));
  const body = element("div", "rejections-body");
  const note = t(outcome === "all_filtered" ? "rejectedNoteAll" : "rejectedNote");
  body.append(element("p", "rejections-note", note));
  for (const item of rejected) {
    const row = element("div", "rejected-item");
    const title = `${t("profileNumber", { id: item.id })}${item.anon_name ? ` · ${item.anon_name}` : ""}`;
    const detail = localizedRejectionDetail({ code: item.primary_reason, detail: item.detail }, query, responseLocale);
    row.append(element("p", "rejected-title", title),
      element("p", "rejected-main", t("primaryReason", { reason: t(reasonLabels[item.primary_reason] || item.primary_reason), detail })));
    const list = element("ul");
    for (const reason of item.all_reasons || []) {
      const entry = element("li");
      const reasonDetail = localizedRejectionDetail(reason, query, responseLocale);
      entry.append(element("strong", "", `${t(reasonLabels[reason.code] || reason.code)}: `),
        document.createTextNode(reasonDetail || ""));
      list.append(entry);
    }
    row.append(list);
    body.append(row);
  }
  disclosure.append(body);
  return disclosure;
}

function parameterLabel(key, value) {
  if (value === null || value === undefined || value === "") return t("notSet");
  if (key === "date") return dateLabel(value);
  if (key === "budget_kzt") return money(value);
  if (key === "hours") return `${value} ${t("hourShort")}`;
  return catalogLabel(value);
}

function renderChanges(previous, response, query) {
  if (!previous || !query) return null;
  const changes = Object.keys(fieldLabels).filter((key) =>
    (previous.query[key] ?? null) !== (query[key] ?? null));
  if (!changes.length) return null;
  const panel = element("section", "change-panel");
  panel.setAttribute("aria-label", t("changedAria"));
  panel.append(element("h3", "", t("changedTitle")));
  const conditions = element("ul", "change-conditions");
  for (const key of changes) {
    conditions.append(element("li", "",
      `${t(fieldLabels[key])}: ${parameterLabel(key, previous.query[key])} → ${parameterLabel(key, query[key])}`));
  }
  panel.append(conditions, element("p", "change-total",
    t("matchingCountChanged", { previous: previous.total, current: response.total_matches })));
  if (changes.length === 1 && changes[0] === "date") {
    panel.append(element("p", "change-note",
      t("dateChangeNote", { previous: previous.excludedByDate, current: response.excluded_by_date })));
  }
  return panel;
}

function renderComparison(cards) {
  if (cards.length < 2) return null;
  const disclosure = element("details", "comparison");
  disclosure.append(element("summary", "", t("compareOptions", { count: cards.length })));
  const scroll = element("div", "comparison-scroll");
  scroll.tabIndex = 0;
  scroll.setAttribute("role", "region");
  scroll.setAttribute("aria-label", t("comparisonAria"));
  const table = element("table", "comparison-table");
  table.append(element("caption", "", t("comparisonCaption")));
  const head = element("thead");
  const heading = element("tr");
  const label = element("th", "", t("condition"));
  label.scope = "col";
  heading.append(label);
  for (const card of cards) {
    const cell = element("th", "", card.anon_name);
    cell.scope = "col";
    heading.append(cell);
  }
  head.append(heading);
  table.append(head);
  const body = element("tbody");
  const rows = [
    [t("priceFrom"), (card) => `${money(card.price_from_kzt)}${card.price_imputed ? ` · ${t("priceImputedYes")}` : ""}`],
    [t("headroom"), (card) => `${money(card.facts.budget_headroom_kzt)} · ${percentFormatter.format(card.facts.budget_headroom_percent)}%`],
    [t("feature"), (card) => card.evidence_excerpt ? `${t("originalRussian")}: ${card.evidence_excerpt}` :
      (card.description?.trim() ? t("featureAbsent") : t("descriptionAbsent"))],
    [t("onDate"), (card) => t(card.facts.not_marked_busy_on_date ? "notBusy" : "availabilityUnknown", { date: dateLabel(card.facts.date) })],
    [t("provenance"), (card) => t(card.synthetic ? "syntheticProfile" : "nonsyntheticProfile")],
  ];
  if (cards.some((card) => card.facts.language)) {
    rows.push([t("requestedLanguage"), (card) => card.facts.language ? catalogLabel(card.facts.language) : t("notSet")]);
  }
  if (cards.some((card) => card.facts.requested_hours != null)) {
    rows.push([t("hours"), (card) => card.facts.max_hours == null
      ? t("durationUnspecified") : t("durationLimit", { hours: card.facts.max_hours })]);
  }
  for (const [title, getValue] of rows) {
    const row = element("tr");
    const cell = element("th", "", title);
    cell.scope = "row";
    row.append(cell);
    for (const card of cards) row.append(element("td", "", getValue(card)));
    body.append(row);
  }
  table.append(body);
  scroll.append(table);
  disclosure.append(scroll, element("p", "comparison-note", t("comparisonNote")));
  return disclosure;
}

function renderFunnel(funnel, total) {
  if (!Array.isArray(funnel) || !funnel.length) return null;
  const labels = { catalog: "funnelAll", city: "funnelCity", category: "funnelCategory", date: "funnelDate", format: "funnelFormat", budget: "funnelBudget", language: "funnelLanguage", hours: "funnelHours", insufficient_data: "funnelData" };
  const section = element("section", "funnel-panel");
  section.append(element("h3", "", t("funnelTitle")));
  const list = element("ol", "funnel-list");
  for (const item of funnel) {
    if (!Object.hasOwn(labels, item.step)) continue;
    const row = element("li", "funnel-step");
    row.append(element("span", "", t(labels[item.step])),
      element("strong", "", numberFormatter.format(item.count)),
      ...(item.applied === false ? [element("small", "", t("funnelUnused"))] : []));
    list.append(row);
  }
  section.append(list, element("p", "funnel-summary", t("funnelShown", { count: total })));
  return section;
}

function renderNearby(dates, query, target, outcome) {
  if (outcome !== "all_filtered" || !Array.isArray(dates)) return null;
  const section = element("section", "nearby-panel");
  section.append(element("h3", "", t("nearbyTitle")));
  if (!dates.length) {
    section.append(element("p", "", t("nearbyNone")));
    return section;
  }
  section.append(element("p", "", t("nearbyIntro")));
  const list = element("div", "nearby-list");
  for (const item of dates.slice(0, 3)) {
    const row = element("div", "nearby-item");
    row.append(element("strong", "", dateLabel(item.date)), element("span", "", t("nearbyCount", { count: item.total_matches })));
    const button = element("button", "nearby-button", t("nearbyChoose"));
    button.type = "button";
    button.addEventListener("click", () => {
      if (target === agentResults && query) setScenarioValues(query);
      fields.date.value = item.date;
      requestMatch();
      if (window.matchMedia("(max-width: 760px)").matches) document.querySelector(".results-column").scrollIntoView({ behavior: "smooth", block: "start" });
    });
    row.append(button);
    list.append(row);
  }
  section.append(list);
  return section;
}

function renderResponse(response, target = resultsElement, query = null, responseLocale = locale, preserve = false) {
  if (!["matched", "no_category_in_city", "all_filtered"].includes(response.outcome) ||
      !Array.isArray(response.cards) || !Array.isArray(response.rejected)) {
    throw new Error(t("invalidResponse"));
  }
  const previous = preserve ? renderedResults.get(target)?.previous : completedResults.get(target);
  const openDetails = preserve ? [...target.querySelectorAll("details")].map((node) => node.open) : [];
  const content = [renderOutcome(response, query, responseLocale)];
  const funnel = renderFunnel(response.funnel, response.total_matches);
  if (funnel) content.push(funnel);
  const changes = renderChanges(previous, response, query);
  if (changes) content.push(changes);
  const nearby = renderNearby(response.nearby_dates, query, target, response.outcome);
  if (nearby) content.push(nearby);
  const comparison = renderComparison(response.cards.slice(0, 3));
  if (comparison) content.push(comparison);
  for (const [index, card] of response.cards.slice(0, 3).entries()) content.push(renderCard(card, index, responseLocale));
  if (response.rejected.length) content.push(renderRejected(response.rejected, response.outcome, responseLocale, query));
  target.replaceChildren(...content);
  if (preserve) [...target.querySelectorAll("details")].forEach((node, index) => { node.open = openDetails[index] ?? false; });
  renderedResults.set(target, { response, query, responseLocale, previous });
  if (query && !preserve) completedResults.set(target, {
    query: { ...query }, total: response.total_matches, excludedByDate: response.excluded_by_date,
  });
}

function agentPlaceholder(message, linkToForm = false) {
  agentPlaceholderState = { key: message, link: linkToForm };
  const panel = element("div", "agent-result-placeholder", t(message));
  if (linkToForm) {
    const link = element("a", "agent-form-link", t("manualFormLink"));
    link.href = "#form-title";
    panel.append(" ", link);
  }
  agentResults.replaceChildren(panel);
}

function setAgentBusy(isBusy) {
  agentInput.disabled = isBusy;
  agentSendButton.disabled = isBusy;
  agentHistory.setAttribute("aria-busy", String(isBusy));
  agentResults.setAttribute("aria-busy", String(isBusy));
  agentSendLabel.textContent = t(isBusy ? "sending" : "send");
}

function appendAgentMessage(who, message) {
  const initial = agentHistory.querySelector(".agent-empty");
  if (initial) initial.remove();
  const bubble = element("div", `agent-message agent-message-${who}`);
  bubble.append(
    element("span", "agent-speaker", t(who)),
    element("p", "", message),
  );
  agentHistory.append(bubble);
  while (agentHistory.querySelectorAll(".agent-message").length > 12) {
    agentHistory.querySelector(".agent-message").remove();
  }
  agentHistory.scrollTop = agentHistory.scrollHeight;
}

function renderAgentParameters(parameters) {
  const list = element("dl", "agent-parameter-list");
  const entries = ["city", "category", "date", "event_format", "budget_kzt", "language", "hours"];
  for (const key of entries) {
    const value = parameters?.[key];
    if (value === null || value === undefined || value === "") continue;
    const formatted = parameterLabel(key, value);
    const pair = element("div", "agent-parameter");
    pair.append(element("dt", "", t(fieldLabels[key])), element("dd", "", formatted));
    list.append(pair);
  }
  agentParameters.replaceChildren(list.childNodes.length ? list : element("p", "", t("parametersNone")));
}

function renderAgentNormalizations(items) {
  agentNormalizations.replaceChildren();
  const valid = Array.isArray(items) ? items.filter((item) => item && item.input && item.field && item.canonical) : [];
  agentNormalizations.hidden = !valid.length;
  if (!valid.length) return;
  agentNormalizations.append(element("strong", "", t("understood")));
  const list = element("ul");
  for (const item of valid) {
    const canonical = parameterLabel(item.field, item.canonical);
    list.append(element("li", "", t("correction", { input: item.input, field: t(fieldLabels[item.field] || "requestParameter"), canonical })));
  }
  agentNormalizations.append(list);
}

function renderAgentSource(body) {
  let brief = "sourceUnknown";
  let detail = "sourceUnknown";
  if (body.source === "unavailable") brief = detail = "aiUnavailable";
  else if (body.status === "clarification") { brief = "sourceBriefClarification"; detail = "sourceClarification"; }
  else if (body.source === "template") { brief = "sourceBriefTemplate"; detail = "sourceTemplate"; }
  else if (body.source === "ai") { brief = body.match?.cards?.length ? "sourceBriefAi" : "sourceBriefClarification"; detail = body.match?.cards?.length ? "sourceAiExcerpts" : "sourceAiNoExcerpts"; }
  agentSource.querySelector("summary").textContent = t(brief);
  agentSource.querySelector("p").textContent = t(detail);
  agentSource.hidden = false;
}

function renderAgentReply(body, responseLocale) {
  if (!body || typeof body.session_id !== "string" ||
      !["clarification", "matched", "unavailable", "error"].includes(body.status) ||
      typeof body.message !== "string" || !body.parameters || typeof body.parameters !== "object") {
    throw new Error(t("invalidAgentResponse"));
  }
  if (body.status === "matched") {
    if (!body.match) throw new Error(t("noMatchResult"));
    renderResponse(body.match, agentResults, body.parameters, responseLocale);
  } else if (body.status === "clarification") {
    renderedResults.delete(agentResults);
    agentPlaceholder("clarifyPlaceholder");
  } else {
    renderedResults.delete(agentResults);
    agentPlaceholder("agentUnavailablePlaceholder", true);
  }
  lastAgentBody = body;
  agentResponseLocale = responseLocale;
  lastAgentParameters = body.parameters;
  lastNormalizations = body.normalizations || [];
  renderAgentParameters(body.parameters);
  renderAgentNormalizations(lastNormalizations);
  renderAgentSource(body);
  agentSessionId = body.session_id;
  appendAgentMessage("assistant", body.message);
  setAgentStatus(body.status === "matched"
    ? (body.match.cards.length
      ? "agentFound"
      : "agentNoMatches")
    : body.status === "clarification"
      ? "agentClarificationStatus"
      : "agentUseForm");
}

async function requestAgent() {
  const message = agentInput.value.trim();
  if (!message) {
    agentInput.setCustomValidity(t("messageRequired"));
    agentInput.reportValidity();
    return;
  }
  agentError.hidden = true;
  agentError.replaceChildren();
  agentErrorState = null;
  if (agentController) agentController.abort();
  const generation = ++agentGeneration;
  const controller = new AbortController();
  agentController = controller;
  setAgentBusy(true);
  setAgentStatus("agentProcessing");
  agentSource.hidden = true;
  renderedResults.delete(agentResults);
  agentPlaceholder("agentProcessingPlaceholder");
  const requestLocale = locale;
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch("/api/agent", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json", "Accept-Language": requestLocale },
      body: JSON.stringify({ session_id: agentSessionId, message }),
      signal: controller.signal,
    });
    const body = await response.json();
    if (generation !== agentGeneration) return;
    if (response.status === 422) {
      setAgentStatus("agent422Status");
      agentPlaceholder("agent422Placeholder");
      agentErrorState = "agent422Error";
      agentError.textContent = t(agentErrorState);
      agentError.hidden = false;
      return;
    }
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    appendAgentMessage("user", message);
    renderAgentReply(body, requestLocale);
    agentInput.value = "";
    agentHistory.scrollTop = agentHistory.scrollHeight;
  } catch (error) {
    if (generation !== agentGeneration) return;
    setAgentStatus("agentErrorStatus");
    agentErrorState = error.name === "AbortError" ? "agentTimeout" : "agentNetworkError";
    agentError.textContent = t(agentErrorState);
    agentError.hidden = false;
    agentPlaceholder("manualAvailable", true);
  } finally {
    clearTimeout(timeout);
    if (generation === agentGeneration) {
      agentController = null;
      setAgentBusy(false);
    }
  }
}

function resetAgent() {
  agentGeneration += 1;
  if (agentController) agentController.abort();
  agentController = null;
  agentSessionId = null;
  completedResults.delete(agentResults);
  renderedResults.delete(agentResults);
  lastAgentBody = null;
  lastAgentParameters = null;
  lastNormalizations = [];
  setAgentBusy(false);
  agentInput.value = "";
  agentInput.setCustomValidity("");
  agentHistory.replaceChildren(element("p", "agent-empty", t("resetEmpty")));
  agentParameters.replaceChildren(element("p", "", t("parametersPlaceholder")));
  renderAgentNormalizations([]);
  agentPlaceholder("agentResultsPlaceholder");
  agentSource.hidden = true;
  agentSource.open = false;
  agentSource.querySelector("summary").textContent = "";
  agentSource.querySelector("p").textContent = "";
  agentError.hidden = true;
  agentError.replaceChildren();
  agentErrorState = null;
  setAgentStatus("resetStatus");
  agentInput.focus();
}

function changeLocale(nextLocale) {
  if (!["ru", "kk", "en"].includes(nextLocale) || nextLocale === locale) return;
  locale = nextLocale;
  try { localStorage.setItem("contractor-locale", locale); } catch (_error) { /* Local storage may be disabled. */ }
  numberFormatter = new Intl.NumberFormat(localeTags[locale], { maximumFractionDigits: 0 });
  percentFormatter = new Intl.NumberFormat(localeTags[locale], { maximumFractionDigits: 1 });
  renderStaticText();
  renderOptions();
  setBusy(Boolean(activeController));
  setAgentBusy(Boolean(agentController));
  statusElement.textContent = t(statusState.key, statusState.values);
  if (validationErrorBody) showError(validationMessage(validationErrorBody));
  else if (errorState) showError(errorState.key, errorState.retry, errorState.values);
  if (!renderedResults.has(resultsElement) && optionsLoaded && !activeController) showInitialState();
  for (const [target, state] of renderedResults) {
    renderResponse(state.response, target, state.query, state.responseLocale, true);
  }
  if (lastAgentParameters) renderAgentParameters(lastAgentParameters);
  renderAgentNormalizations(lastNormalizations);
  if (lastAgentBody && !agentSource.hidden) renderAgentSource(lastAgentBody);
  agentStatus.textContent = t(agentStatusState.key, agentStatusState.values);
  if (agentErrorState) agentError.textContent = t(agentErrorState);
  for (const node of agentHistory.querySelectorAll(".agent-message")) {
    node.querySelector(".agent-speaker").textContent = t(node.classList.contains("agent-message-user") ? "user" : "assistant");
  }
  const empty = agentHistory.querySelector(".agent-empty");
  if (empty) empty.textContent = t("resetEmpty");
  if (!renderedResults.has(agentResults)) agentPlaceholder(agentPlaceholderState.key, agentPlaceholderState.link);
}

for (const button of localeButtons) button.addEventListener("click", () => changeLocale(button.dataset.locale));

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

agentForm.addEventListener("submit", (event) => {
  event.preventDefault();
  requestAgent();
});
agentInput.addEventListener("input", () => agentInput.setCustomValidity(""));
agentInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    agentForm.requestSubmit();
  }
});
agentResetButton.addEventListener("click", resetAgent);

renderStaticText();
loadOptions();
