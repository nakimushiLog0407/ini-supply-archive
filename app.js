const calendar = document.getElementById("calendar");
const currentMonth = document.getElementById("currentMonth");
const selectedDate = document.getElementById("selectedDate");
const supplyList = document.getElementById("supplyList");

const prevMonthButton = document.getElementById("prevMonth");
const nextMonthButton = document.getElementById("nextMonth");

let supplies = [];

const today = new Date();

let displayYear = today.getFullYear();
let displayMonth = today.getMonth();

let selectedDateKey = formatDateKey(
  today.getFullYear(),
  today.getMonth(),
  today.getDate()
);

/* =========================
   供給データを読み込む
========================= */

async function loadSupplies() {
  try {
    const response = await fetch("data/supplies.json");

    if (!response.ok) {
      throw new Error("供給データを読み込めませんでした。");
    }

    supplies = await response.json();

    renderCalendar();
    renderSelectedDate();

  } catch (error) {
    console.error(error);

    supplyList.innerHTML = `
      <p class="no-supplies">
        データの読み込みに失敗しました。
      </p>
    `;
  }
}

/* =========================
   日付を YYYY-MM-DD にする
========================= */

function formatDateKey(year, month, day) {
  const formattedMonth = String(month + 1).padStart(2, "0");
  const formattedDay = String(day).padStart(2, "0");

  return `${year}-${formattedMonth}-${formattedDay}`;
}

/* =========================
   カレンダーを描画
========================= */

function renderCalendar() {
  calendar.innerHTML = "";

  currentMonth.textContent =
    `${displayYear}年${displayMonth + 1}月`;

  const firstDay = new Date(
    displayYear,
    displayMonth,
    1
  );

  const lastDate = new Date(
    displayYear,
    displayMonth + 1,
    0
  ).getDate();

  /*
    JavaScriptでは
    日=0 月=1 火=2 ... 土=6

    今回のカレンダーは月曜始まりなので変換する
  */
  const startPosition =
    (firstDay.getDay() + 6) % 7;

  /* 月初より前の空白 */
  for (let i = 0; i < startPosition; i++) {
    const emptyCell = document.createElement("div");
    emptyCell.className = "calendar-day empty";
    calendar.appendChild(emptyCell);
  }

  /* 日付 */
  for (let day = 1; day <= lastDate; day++) {
    const dateKey = formatDateKey(
      displayYear,
      displayMonth,
      day
    );

    const dayButton = document.createElement("button");

    dayButton.type = "button";
    dayButton.className = "calendar-day";

    /* 今日 */
    if (
      displayYear === today.getFullYear() &&
      displayMonth === today.getMonth() &&
      day === today.getDate()
    ) {
      dayButton.classList.add("today");
    }

    /* 選択中の日 */
    if (dateKey === selectedDateKey) {
      dayButton.classList.add("selected");
    }

    const dayNumber = document.createElement("span");
    dayNumber.className = "day-number";
    dayNumber.textContent = day;

    dayButton.appendChild(dayNumber);

    /*
      この日にYouTube供給が存在するか確認。
      何本あっても赤い●は1つだけ。
    */
    const hasYouTube = supplies.some(
      supply =>
        supply.date === dateKey &&
        supply.type === "youtube"
    );

    if (hasYouTube) {
      const dots = document.createElement("div");
      dots.className = "supply-dots";

      const dot = document.createElement("span");
      dot.className = "dot youtube-dot";

      dots.appendChild(dot);
      dayButton.appendChild(dots);
    }

    /* 日付をタップ */
    dayButton.addEventListener("click", () => {
      selectedDateKey = dateKey;

      renderCalendar();
      renderSelectedDate();
    });

    calendar.appendChild(dayButton);
  }
}

/* =========================
   選択日の供給を表示
========================= */

function renderSelectedDate() {
  const [year, month, day] =
    selectedDateKey.split("-").map(Number);

  selectedDate.textContent =
    `${year}年${month}月${day}日`;

  const selectedSupplies = supplies.filter(
    supply => supply.date === selectedDateKey
  );

  supplyList.innerHTML = "";

  if (selectedSupplies.length === 0) {
    supplyList.innerHTML = `
      <p class="no-supplies">
        この日の供給はありません。
      </p>
    `;

    return;
  }

  /*
    現時点ではYouTubeのみ。
    将来ここにTikTok、TVなどを追加できる。
  */
  const youtubeSupplies = selectedSupplies.filter(
    supply => supply.type === "youtube"
  );

  if (youtubeSupplies.length > 0) {
    const category = document.createElement("div");
    category.className = "supply-category";

    const categoryTitle = document.createElement("div");
    categoryTitle.className = "supply-category-title";

    categoryTitle.innerHTML = `
      <span class="dot youtube-dot"></span>
      <span>YouTube</span>
    `;

    category.appendChild(categoryTitle);

    youtubeSupplies.forEach(supply => {
      const item = document.createElement("button");

      item.type = "button";
      item.className = "supply-item";

      item.innerHTML = `
        <span class="supply-title"></span>
        <span class="supply-arrow">›</span>
      `;

      item.querySelector(".supply-title").textContent =
        supply.title;

      /*
        DETAILページはまだ作っていないので、
        現時点では押しても何もしない。
      */

      category.appendChild(item);
    });

    supplyList.appendChild(category);
  }
}

/* =========================
   前月へ
========================= */

prevMonthButton.addEventListener("click", () => {
  displayMonth--;

  if (displayMonth < 0) {
    displayMonth = 11;
    displayYear--;
  }

  renderCalendar();
});

/* =========================
   翌月へ
========================= */

nextMonthButton.addEventListener("click", () => {
  displayMonth++;

  if (displayMonth > 11) {
    displayMonth = 0;
    displayYear++;
  }

  renderCalendar();
});

/* =========================
   開始
========================= */

loadSupplies();
