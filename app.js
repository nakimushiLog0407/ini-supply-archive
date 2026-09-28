const calendar = document.getElementById("calendar");
const currentMonth = document.getElementById("currentMonth");
const selectedDate = document.getElementById("selectedDate");
const supplyList = document.getElementById("supplyList");

const prevMonthButton = document.getElementById("prevMonth");
const nextMonthButton = document.getElementById("nextMonth");

const monthPickerButton =
  document.getElementById("monthPickerButton");

const monthPicker =
  document.getElementById("monthPicker");

const yearSelect =
  document.getElementById("yearSelect");

const monthSelect =
  document.getElementById("monthSelect");

const monthPickerCancel =
  document.getElementById("monthPickerCancel");

const monthPickerGo =
  document.getElementById("monthPickerGo");

/* =========================
   画面
========================= */

const calendarView =
  document.getElementById("calendarView");

const detailView =
  document.getElementById("detailView");

const bottomNav =
  document.getElementById("bottomNav");

/* =========================
   DETAIL
========================= */

const detailBackButton =
  document.getElementById("detailBackButton");

const detailThumbnail =
  document.getElementById("detailThumbnail");

const detailTitle =
  document.getElementById("detailTitle");

const detailDate =
  document.getElementById("detailDate");

const detailYoutubeLink =
  document.getElementById("detailYoutubeLink");

/* =========================
   基本データ
========================= */

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
    const response =
      await fetch("data/supplies.json");

    if (!response.ok) {
      throw new Error(
        "供給データを読み込めませんでした。"
      );
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
  const formattedMonth =
    String(month + 1).padStart(2, "0");

  const formattedDay =
    String(day).padStart(2, "0");

  return (
    `${year}-${formattedMonth}-${formattedDay}`
  );
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

    今回は月曜始まりなので変換
  */
  const startPosition =
    (firstDay.getDay() + 6) % 7;

  /* 月初より前の空白 */

  for (
    let i = 0;
    i < startPosition;
    i++
  ) {
    const emptyCell =
      document.createElement("div");

    emptyCell.className =
      "calendar-day empty";

    calendar.appendChild(emptyCell);
  }

  /* 日付 */

  for (
    let day = 1;
    day <= lastDate;
    day++
  ) {

    const dateKey = formatDateKey(
      displayYear,
      displayMonth,
      day
    );

    const dayButton =
      document.createElement("button");

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

    const dayNumber =
      document.createElement("span");

    dayNumber.className = "day-number";
    dayNumber.textContent = day;

    dayButton.appendChild(dayNumber);

    /*
      この日にYouTube供給があるか確認。
      動画が何本あっても赤い●は1つ。
    */

    const hasYouTube = supplies.some(
      supply =>
        supply.date === dateKey &&
        supply.type === "youtube"
    );

    if (hasYouTube) {

      const dots =
        document.createElement("div");

      dots.className = "supply-dots";

      const dot =
        document.createElement("span");

      dot.className =
        "dot youtube-dot";

      dots.appendChild(dot);

      dayButton.appendChild(dots);
    }

    /* 日付をタップ */

    dayButton.addEventListener(
      "click",
      () => {

        selectedDateKey = dateKey;

        renderCalendar();
        renderSelectedDate();

      }
    );

    calendar.appendChild(dayButton);
  }
}

/* =========================
   選択日の供給を表示
========================= */

function renderSelectedDate() {

  const [year, month, day] =
    selectedDateKey
      .split("-")
      .map(Number);

  selectedDate.textContent =
    `${year}年${month}月${day}日`;

  const selectedSupplies =
    supplies.filter(
      supply =>
        supply.date === selectedDateKey
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
    将来ここへ別カテゴリを追加できる。
  */

  const youtubeSupplies =
    selectedSupplies.filter(
      supply =>
        supply.type === "youtube"
    );

  if (youtubeSupplies.length > 0) {

    const category =
      document.createElement("div");

    category.className =
      "supply-category";

    const categoryTitle =
      document.createElement("div");

    categoryTitle.className =
      "supply-category-title";

    categoryTitle.innerHTML = `
      <span class="dot youtube-dot"></span>
      <span>YouTube</span>
    `;

    category.appendChild(
      categoryTitle
    );

    youtubeSupplies.forEach(
      supply => {

        const item =
          document.createElement("button");

        item.type = "button";
        item.className =
          "supply-item";

        item.innerHTML = `
          <span class="supply-title"></span>
          <span class="supply-arrow">›</span>
        `;

        item
          .querySelector(".supply-title")
          .textContent =
          supply.title;

        /*
          タイトルを押したら
          DETAIL画面を開く
        */

        item.addEventListener(
          "click",
          () => {
            openDetail(supply);
          }
        );

        category.appendChild(item);
      }
    );

    supplyList.appendChild(category);
  }
}

/* =========================
   DETAILを開く
========================= */

function openDetail(supply) {

  /*
    videoIdから
    YouTube URLを生成
  */

  const youtubeUrl =
    `https://www.youtube.com/watch?v=${supply.videoId}`;

  /*
    videoIdから
    サムネイルURLを生成

    maxresdefaultを使用。
    将来API取得時には
    サムネイル情報を直接使うことも可能。
  */

  const thumbnailUrl =
    `https://i.ytimg.com/vi/${supply.videoId}/maxresdefault.jpg`;

  /* サムネイル */

  detailThumbnail.src =
    thumbnailUrl;

  detailThumbnail.alt =
    `${supply.title}のサムネイル`;

  /* タイトル */

  detailTitle.textContent =
    supply.title;

  /* 公開日 */

  const [year, month, day] =
    supply.date
      .split("-")
      .map(Number);

  detailDate.textContent =
    `${year}年${month}月${day}日`;

  /* YouTubeリンク */

  detailYoutubeLink.href =
    youtubeUrl;

  /* 画面切り替え */

  calendarView.hidden = true;
  detailView.hidden = false;
  bottomNav.hidden = true;

  /*
    DETAILを開いたら
    ページ上部へ移動
  */

  window.scrollTo({
    top: 0,
    behavior: "instant"
  });
}

/* =========================
   DETAILから戻る
========================= */

function closeDetail() {

  detailView.hidden = true;
  calendarView.hidden = false;
  bottomNav.hidden = false;

  /*
    カレンダーの年月や
    選択日は変更しない
  */

}

/* 戻るボタン */

detailBackButton.addEventListener(
  "click",
  () => {
    closeDetail();
  }
);

/* =========================
   前月へ
========================= */

prevMonthButton.addEventListener(
  "click",
  () => {

    displayMonth--;

    if (displayMonth < 0) {
      displayMonth = 11;
      displayYear--;
    }

    renderCalendar();

  }
);

/* =========================
   翌月へ
========================= */

nextMonthButton.addEventListener(
  "click",
  () => {

    displayMonth++;

    if (displayMonth > 11) {
      displayMonth = 0;
      displayYear++;
    }

    renderCalendar();

  }
);

/* =========================
   年月選択の選択肢を作る
========================= */

function createMonthPickerOptions() {

  yearSelect.innerHTML = "";
  monthSelect.innerHTML = "";

  /*
    2021年から現在年まで
  */

  const startYear = 2021;

  const currentYear =
    today.getFullYear();

  for (
    let year = currentYear;
    year >= startYear;
    year--
  ) {

    const option =
      document.createElement("option");

    option.value = year;

    option.textContent =
      `${year}年`;

    yearSelect.appendChild(option);
  }

  /* 1月〜12月 */

  for (
    let month = 1;
    month <= 12;
    month++
  ) {

    const option =
      document.createElement("option");

    option.value = month;

    option.textContent =
      `${month}月`;

    monthSelect.appendChild(option);
  }
}

/* =========================
   年月選択を開く
========================= */

monthPickerButton.addEventListener(
  "click",
  () => {

    yearSelect.value =
      displayYear;

    monthSelect.value =
      displayMonth + 1;

    monthPicker.hidden = false;

  }
);

/* =========================
   年月選択をキャンセル
========================= */

monthPickerCancel.addEventListener(
  "click",
  () => {

    monthPicker.hidden = true;

  }
);

/* =========================
   選択した年月へ移動
========================= */

monthPickerGo.addEventListener(
  "click",
  () => {

    const selectedYear =
      Number(yearSelect.value);

    const selectedMonth =
      Number(monthSelect.value);

    displayYear =
      selectedYear;

    displayMonth =
      selectedMonth - 1;

    monthPicker.hidden = true;

    renderCalendar();

  }
);

/* =========================
   背景を押したら年月選択を閉じる
========================= */

monthPicker.addEventListener(
  "click",
  event => {

    if (event.target === monthPicker) {
      monthPicker.hidden = true;
    }

  }
);

/* =========================
   初期設定
========================= */

createMonthPickerOptions();

loadSupplies();
