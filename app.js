const calendar =
  document.getElementById("calendar");

const currentMonth =
  document.getElementById("currentMonth");

const selectedDate =
  document.getElementById("selectedDate");

const supplyList =
  document.getElementById("supplyList");


const prevMonthButton =
  document.getElementById("prevMonth");

const nextMonthButton =
  document.getElementById("nextMonth");


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

const exploreView =
  document.getElementById("exploreView");

const detailView =
  document.getElementById("detailView");

const bottomNav =
  document.getElementById("bottomNav");


/* =========================
   下部ナビ
========================= */

const calendarNavButton =
  document.getElementById("calendarNavButton");

const exploreNavButton =
  document.getElementById("exploreNavButton");


/* =========================
   EXPLORE
========================= */

const exploreSearchInput =
  document.getElementById("exploreSearchInput");

const exploreResultLabel =
  document.getElementById("exploreResultLabel");

const exploreResultCount =
  document.getElementById("exploreResultCount");

const exploreList =
  document.getElementById("exploreList");

const exploreLoadMore =
  document.getElementById("exploreLoadMore");


/* =========================
   EXPLORE カテゴリ
========================= */

const exploreCategoryButton =
  document.getElementById("exploreCategoryButton");

const exploreCategoryLabel =
  document.getElementById("exploreCategoryLabel");

const categorySheet =
  document.getElementById("categorySheet");

const categorySheetClose =
  document.getElementById("categorySheetClose");

const categorySheetOptions =
  document.querySelectorAll(
    ".category-sheet-option"
  );


/* =========================
   DETAIL
========================= */

const detailBackButton =
  document.getElementById("detailBackButton");

const detailThumbnailWrapper =
  document.getElementById(
    "detailThumbnailWrapper"
  );

const detailThumbnail =
  document.getElementById("detailThumbnail");

const detailType =
  document.getElementById("detailType");

const detailTitle =
  document.getElementById("detailTitle");

const detailDate =
  document.getElementById("detailDate");

const detailMember =
  document.getElementById("detailMember");

const detailExternalLink =
  document.getElementById(
    "detailExternalLink"
  );

const detailExternalLinkText =
  document.getElementById(
    "detailExternalLinkText"
  );


/* =========================
   基本データ
========================= */

let supplies = [];

const today = new Date();

let displayYear =
  today.getFullYear();

let displayMonth =
  today.getMonth();

let selectedDateKey =
  formatDateKey(
    today.getFullYear(),
    today.getMonth(),
    today.getDate()
  );


/* =========================
   現在のメイン画面
========================= */

/*
  "calendar"
  "explore"

  DETAILから戻るときに使用
*/

let currentMainView = "calendar";


/* =========================
   EXPLORE表示設定
========================= */

const EXPLORE_PAGE_SIZE = 50;

let exploreVisibleCount =
  EXPLORE_PAGE_SIZE;


/* =========================
   EXPLOREカテゴリ設定
========================= */

/*
  all
  youtube
  member_diary
  movie
*/

let selectedExploreCategory =
  "all";


const exploreCategoryNames = {
  all: "すべて",
  youtube: "YouTube",
  member_diary: "Member Diary",
  movie: "Movie"
};


/* =========================
   JSONを読み込む
========================= */

async function fetchJson(path) {

  const response =
    await fetch(path);

  if (!response.ok) {

    throw new Error(
      `${path} を読み込めませんでした。`
    );

  }

  const data =
    await response.json();

  if (!Array.isArray(data)) {

    throw new Error(
      `${path} の形式が不正です。`
    );

  }

  return data;

}


/* =========================
   供給データを読み込む

   保存ファイルは分離したまま、
   ブラウザ上だけで統合する。
========================= */

async function loadSupplies() {

  try {

    const [
      youtubeSupplies,
      memberDiarySupplies,
      movieSupplies
    ] = await Promise.all([
      fetchJson("data/youtube.json"),
      fetchJson("data/member_diary.json"),
      fetchJson("data/movie.json")
    ]);

    supplies = [
      ...youtubeSupplies,
      ...memberDiarySupplies,
      ...movieSupplies
    ];

    renderCalendar();

    renderSelectedDate();

    renderExplore();

  } catch (error) {

    console.error(error);

    supplyList.innerHTML = `
      <p class="no-supplies">
        データの読み込みに失敗しました。
      </p>
    `;

    exploreList.innerHTML = `
      <p class="explore-empty">
        データの読み込みに失敗しました。
      </p>
    `;

  }

}


/* =========================
   日付を YYYY-MM-DD にする
========================= */

function formatDateKey(
  year,
  month,
  day
) {

  const formattedMonth =
    String(month + 1)
      .padStart(2, "0");

  const formattedDay =
    String(day)
      .padStart(2, "0");

  return (
    `${year}-${formattedMonth}-${formattedDay}`
  );

}


/* =========================
   YYYY-MM-DD を
   日本語の日付にする
========================= */

function formatDisplayDate(dateString) {

  const [year, month, day] =
    dateString
      .split("-")
      .map(Number);

  return `${year}年${month}月${day}日`;

}


/* =========================
   供給の並び順

   YouTubeにはpublishedAtがあるので
   同日なら公開時刻を使用。

   Member Diaryは公開時刻がないため
   date → ID の順を使用。
========================= */

function compareSuppliesAscending(
  a,
  b
) {

  const aDate =
    a.publishedAt ||
    a.date ||
    "";

  const bDate =
    b.publishedAt ||
    b.date ||
    "";

  const dateComparison =
    aDate.localeCompare(
      bDate
    );

  if (dateComparison !== 0) {

    return dateComparison;

  }

  return String(
    a.id || ""
  ).localeCompare(
    String(
      b.id || ""
    ),
    "ja",
    {
      numeric: true
    }
  );

}


/* =========================
   カレンダーを描画
========================= */

function renderCalendar() {

  calendar.innerHTML = "";

  currentMonth.textContent =
    `${displayYear}年${displayMonth + 1}月`;

  const firstDay =
    new Date(
      displayYear,
      displayMonth,
      1
    );

  const lastDate =
    new Date(
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

    calendar.appendChild(
      emptyCell
    );

  }


  /* 日付 */

  for (
    let day = 1;
    day <= lastDate;
    day++
  ) {

    const dateKey =
      formatDateKey(
        displayYear,
        displayMonth,
        day
      );

    const dayButton =
      document.createElement("button");

    dayButton.type = "button";

    dayButton.className =
      "calendar-day";


    /* 今日 */

    if (
      displayYear ===
        today.getFullYear() &&
      displayMonth ===
        today.getMonth() &&
      day ===
        today.getDate()
    ) {

      dayButton.classList.add(
        "today"
      );

    }


    /* 選択中の日 */

    if (
      dateKey === selectedDateKey
    ) {

      dayButton.classList.add(
        "selected"
      );

    }


    const dayNumber =
      document.createElement("span");

    dayNumber.className =
      "day-number";

    dayNumber.textContent =
      day;

    dayButton.appendChild(
      dayNumber
    );


    /* =====================
       この日の供給カテゴリ
    ===================== */

    const hasYouTube =
      supplies.some(
        supply =>
          supply.date === dateKey &&
          supply.type === "youtube"
      );

    const hasFcContents =
      supplies.some(
        supply =>
          supply.date === dateKey &&
          supply.group === "fc"
      );


    if (
      hasYouTube ||
      hasFcContents
    ) {

      const dots =
        document.createElement("div");

      dots.className =
        "supply-dots";


      if (hasYouTube) {

        const youtubeDot =
          document.createElement("span");

        youtubeDot.className =
          "dot youtube-dot";

        dots.appendChild(
          youtubeDot
        );

      }


      if (hasFcContents) {

        const fcDot =
          document.createElement("span");

        fcDot.className =
          "dot fc-dot";

        dots.appendChild(
          fcDot
        );

      }


      dayButton.appendChild(
        dots
      );

    }


    /* 日付をタップ */

    dayButton.addEventListener(
      "click",
      () => {

        selectedDateKey =
          dateKey;

        renderCalendar();

        renderSelectedDate();

      }
    );


    calendar.appendChild(
      dayButton
    );

  }

}


/* =========================
   一覧用の供給ボタンを作る
========================= */

function createSupplyItem(
  supply,
  fromView,
  showMember = false
) {

  const item =
    document.createElement(
      "button"
    );

  item.type = "button";

  item.className =
    "supply-item";


  const text =
    document.createElement(
      "span"
    );

  text.className =
    "supply-item-text";


  const title =
    document.createElement(
      "span"
    );

  title.className =
    "supply-title";

  title.textContent =
    supply.title;

  text.appendChild(
    title
  );


  if (
    showMember &&
    supply.member
  ) {

    const member =
      document.createElement(
        "span"
      );

    member.className =
      "supply-member";

    member.textContent =
      supply.member;

    text.appendChild(
      member
    );

  }


  const arrow =
    document.createElement(
      "span"
    );

  arrow.className =
    "supply-arrow";

  arrow.textContent =
    "›";


  item.appendChild(
    text
  );

  item.appendChild(
    arrow
  );


  item.addEventListener(
    "click",
    () => {

      openDetail(
        supply,
        fromView
      );

    }
  );


  return item;

}


/* =========================
   選択日の供給を表示
========================= */

function renderSelectedDate() {

  selectedDate.textContent =
    formatDisplayDate(
      selectedDateKey
    );


  const selectedSupplies =
    supplies
      .filter(
        supply =>
          supply.date ===
          selectedDateKey
      )
      .sort(
        compareSuppliesAscending
      );


  supplyList.innerHTML = "";


  if (
    selectedSupplies.length === 0
  ) {

    supplyList.innerHTML = `
      <p class="no-supplies">
        この日の供給はありません。
      </p>
    `;

    return;

  }


  /* =====================
     YouTube
  ===================== */

  const youtubeSupplies =
    selectedSupplies.filter(
      supply =>
        supply.type === "youtube"
    );


  if (
    youtubeSupplies.length > 0
  ) {

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

        category.appendChild(
          createSupplyItem(
            supply,
            "calendar",
            false
          )
        );

      }
    );


    supplyList.appendChild(
      category
    );

  }


  /* =====================
     FC CONTENTS
     └ Member Diary
  ===================== */

  const memberDiarySupplies =
    selectedSupplies.filter(
      supply =>
        supply.type ===
        "member_diary"
    );


  if (
    memberDiarySupplies.length > 0
  ) {

    const category =
      document.createElement("div");

    category.className =
      "supply-category";


    const categoryTitle =
      document.createElement("div");

    categoryTitle.className =
      "supply-category-title";

    categoryTitle.innerHTML = `
      <span class="dot fc-dot"></span>
      <span>Member Diary</span>
    `;


    category.appendChild(
      categoryTitle
    );


    memberDiarySupplies.forEach(
      supply => {

        category.appendChild(
          createSupplyItem(
            supply,
            "calendar",
            true
          )
        );

      }
    );


    supplyList.appendChild(
      category
    );

  }


  /* =====================
     FC CONTENTS
     └ Movie
  ===================== */

  const movieSupplies =
    selectedSupplies.filter(
      supply =>
        supply.type === "movie"
    );


  if (
    movieSupplies.length > 0
  ) {

    const category =
      document.createElement("div");

    category.className =
      "supply-category";


    const categoryTitle =
      document.createElement("div");

    categoryTitle.className =
      "supply-category-title";

    categoryTitle.innerHTML = `
      <span class="dot fc-dot"></span>
      <span>Movie</span>
    `;


    category.appendChild(
      categoryTitle
    );


    movieSupplies.forEach(
      supply => {

        category.appendChild(
          createSupplyItem(
            supply,
            "calendar",
            false
          )
        );

      }
    );


    supplyList.appendChild(
      category
    );

  }

}


  /* =====================
     YouTube
  ===================== */

  const youtubeSupplies =
    selectedSupplies.filter(
      supply =>
        supply.type === "youtube"
    );


  if (
    youtubeSupplies.length > 0
  ) {

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

        category.appendChild(
          createSupplyItem(
            supply,
            "calendar",
            false
          )
        );

      }
    );


    supplyList.appendChild(
      category
    );

  }


  /* =====================
     FC CONTENTS
     └ Member Diary
  ===================== */

  const memberDiarySupplies =
    selectedSupplies.filter(
      supply =>
        supply.type ===
        "member_diary"
    );


  if (
    memberDiarySupplies.length > 0
  ) {

    const category =
      document.createElement("div");

    category.className =
      "supply-category";


    const categoryTitle =
      document.createElement("div");

    categoryTitle.className =
      "supply-category-title";

    categoryTitle.innerHTML = `
      <span class="dot fc-dot"></span>
      <span>Member Diary</span>
    `;


    category.appendChild(
      categoryTitle
    );


    memberDiarySupplies.forEach(
      supply => {

        category.appendChild(
          createSupplyItem(
            supply,
            "calendar",
            true
          )
        );

      }
    );


    supplyList.appendChild(
      category
    );

  }

}


/* ==========================================================
   EXPLORE
   ========================================================== */


/* =========================
   カテゴリ条件に一致するか
========================= */

function matchesExploreCategory(
  supply
) {

  if (
    selectedExploreCategory ===
    "all"
  ) {

    return true;

  }


  if (
    selectedExploreCategory ===
    "youtube"
  ) {

    return (
      supply.type === "youtube"
    );

  }


  if (
    selectedExploreCategory ===
    "member_diary"
  ) {

    return (
      supply.type ===
      "member_diary"
    );

  }

    if (
    selectedExploreCategory ===
    "movie"
  ) {

    return (
      supply.type === "movie"
    );

  }


  return true;

}


/* =========================
   EXPLORE用データを作る
========================= */

function getExploreSupplies() {

  const rawQuery =
    exploreSearchInput.value
      .trim()
      .toLocaleLowerCase();


  /*
    新しい公開日時から順にする。

    YouTubeはpublishedAt、
    Member Diaryはdateを使用。
  */

  const sortedSupplies =
    [...supplies].sort(
      (a, b) => {

        const aDate =
          a.publishedAt ||
          a.date ||
          "";

        const bDate =
          b.publishedAt ||
          b.date ||
          "";

        const dateComparison =
          bDate.localeCompare(
            aDate
          );

        if (
          dateComparison !== 0
        ) {

          return dateComparison;

        }

        return String(
          b.id || ""
        ).localeCompare(
          String(
            a.id || ""
          ),
          "ja",
          {
            numeric: true
          }
        );

      }
    );


  /*
    まずカテゴリで絞り込む
  */

  const categoryFiltered =
    sortedSupplies.filter(
      supply =>
        matchesExploreCategory(
          supply
        )
    );


  /*
    キーワードなしなら
    カテゴリ絞り込み結果を
    そのまま返す
  */

  if (!rawQuery) {

    return categoryFiltered;

  }


  /*
    空白区切りで
    複数キーワード化

    例：
    木村 2021
  */

  const keywords =
    rawQuery
      .split(/\s+/)
      .filter(Boolean);


  return categoryFiltered.filter(
    supply => {

      const title =
        String(
          supply.title || ""
        ).toLocaleLowerCase();


      /*
        YouTube
        → タイトルのみ検索
      */

      if (
        supply.type === "youtube"
      ) {

        return keywords.every(
          keyword =>
            title.includes(
              keyword
            )
        );

      }


      /*
        Member Diary
        → タイトル＋メンバー名
      */

      if (
        supply.type ===
        "member_diary"
      ) {

        const member =
          String(
            supply.member || ""
          ).toLocaleLowerCase();

        const searchableText =
          `${title} ${member}`;

        return keywords.every(
          keyword =>
            searchableText.includes(
              keyword
            )
        );

      }


      /*
        将来別の供給種別を
        追加した場合は
        タイトルを検索対象にする
      */

      return keywords.every(
        keyword =>
          title.includes(
            keyword
          )
      );

    }
  );

}


/* =========================
   EXPLOREを描画
========================= */

function renderExplore() {

  const query =
    exploreSearchInput.value
      .trim();


  const filteredSupplies =
    getExploreSupplies();


  /* =====================
     検索結果ヘッダー
  ===================== */

  if (query) {

    exploreResultLabel.textContent =
      "SEARCH RESULTS";

  } else {

    if (
      selectedExploreCategory ===
      "all"
    ) {

      exploreResultLabel.textContent =
        "ALL";

    } else {

      exploreResultLabel.textContent =
        exploreCategoryNames[
          selectedExploreCategory
        ] || "ALL";

    }

  }


  exploreResultCount.textContent =
    `${filteredSupplies.length.toLocaleString()}件`;


  /* 一覧を空にする */

  exploreList.innerHTML = "";


  /* 検索結果なし */

  if (
    filteredSupplies.length === 0
  ) {

    exploreList.innerHTML = `
      <p class="explore-empty">
        該当する供給はありません。
      </p>
    `;

    exploreLoadMore.hidden =
      true;

    return;

  }


  /* 今回表示する分 */

  const visibleSupplies =
    filteredSupplies.slice(
      0,
      exploreVisibleCount
    );


  visibleSupplies.forEach(
    supply => {

      const item =
        document.createElement(
          "button"
        );

      item.type = "button";

      item.className =
        "explore-item";


      /* 公開日 */

      const date =
        document.createElement(
          "span"
        );

      date.className =
        "explore-item-date";

      date.textContent =
        formatDisplayDate(
          supply.date
        );


      /* カテゴリ */

      const category =
        document.createElement(
          "span"
        );

      category.className =
        "explore-item-category";


            if (
        supply.type === "youtube"
      ) {

        category.innerHTML = `
          <span class="dot youtube-dot"></span>
          <span>YouTube</span>
        `;

      } else if (
        supply.type ===
        "member_diary"
      ) {

        category.innerHTML = `
          <span class="dot fc-dot"></span>
          <span>Member Diary</span>
        `;

      } else if (
        supply.type === "movie"
      ) {

        category.innerHTML = `
          <span class="dot fc-dot"></span>
          <span>Movie</span>
        `;

      } else {

        category.textContent =
          supply.type || "";

      }


      /* =====================
         タイトル・メンバー
      ===================== */

      const main =
        document.createElement(
          "span"
        );

      main.className =
        "explore-item-main";


      const text =
        document.createElement(
          "span"
        );

      text.className =
        "explore-item-text";


      const title =
        document.createElement(
          "span"
        );

      title.className =
        "explore-item-title";

      title.textContent =
        supply.title;

      text.appendChild(
        title
      );


      if (
        supply.type ===
          "member_diary" &&
        supply.member
      ) {

        const member =
          document.createElement(
            "span"
          );

        member.className =
          "explore-item-member";

        member.textContent =
          supply.member;

        text.appendChild(
          member
        );

      }


      const arrow =
        document.createElement(
          "span"
        );

      arrow.className =
        "explore-item-arrow";

      arrow.textContent =
        "›";


      main.appendChild(
        text
      );

      main.appendChild(
        arrow
      );


      item.appendChild(
        date
      );

      item.appendChild(
        category
      );

      item.appendChild(
        main
      );


      /* DETAILへ */

      item.addEventListener(
        "click",
        () => {

          openDetail(
            supply,
            "explore"
          );

        }
      );


      exploreList.appendChild(
        item
      );

    }
  );


  /*
    まだ表示していない供給が
    残っている場合だけ表示
  */

  exploreLoadMore.hidden =
    exploreVisibleCount >=
    filteredSupplies.length;

}


/* =========================
   EXPLORE検索
========================= */

exploreSearchInput.addEventListener(
  "input",
  () => {

    exploreVisibleCount =
      EXPLORE_PAGE_SIZE;

    renderExplore();

  }
);


/* =========================
   EXPLORE さらに表示
========================= */

exploreLoadMore.addEventListener(
  "click",
  () => {

    exploreVisibleCount +=
      EXPLORE_PAGE_SIZE;

    renderExplore();

  }
);


/* ==========================================================
   EXPLORE カテゴリボトムシート
   ========================================================== */


/* =========================
   ボトムシートを開く
========================= */

function openCategorySheet() {

  categorySheet.hidden =
    false;

  exploreCategoryButton.setAttribute(
    "aria-expanded",
    "true"
  );

  /*
    シートを開いた時点で
    現在選択中のカテゴリに
    チェックを付け直す
  */

  updateCategorySheetSelection();

}


/* =========================
   ボトムシートを閉じる
========================= */

function closeCategorySheet() {

  categorySheet.hidden =
    true;

  exploreCategoryButton.setAttribute(
    "aria-expanded",
    "false"
  );

}


/* =========================
   選択状態を更新
========================= */

function updateCategorySheetSelection() {

  categorySheetOptions.forEach(
    option => {

      const category =
        option.dataset.category;

      const check =
        option.querySelector(
          ".category-sheet-check"
        );


      if (
        category ===
        selectedExploreCategory
      ) {

        option.classList.add(
          "selected"
        );

        if (check) {

          check.textContent =
            "✓";

        }

      } else {

        option.classList.remove(
          "selected"
        );

        if (check) {

          check.textContent =
            "";

        }

      }

    }
  );


  /*
    EXPLORE本体の
    カテゴリ名も更新
  */

  exploreCategoryLabel.textContent =
    exploreCategoryNames[
      selectedExploreCategory
    ] || "すべて";

}


/* =========================
   カテゴリボタン
========================= */

exploreCategoryButton.addEventListener(
  "click",
  () => {

    openCategorySheet();

  }
);


/* =========================
   ×ボタン
========================= */

categorySheetClose.addEventListener(
  "click",
  () => {

    closeCategorySheet();

  }
);


/* =========================
   カテゴリを選択
========================= */

categorySheetOptions.forEach(
  option => {

    option.addEventListener(
      "click",
      () => {

        const category =
          option.dataset.category;


        if (
          !category
        ) {

          return;

        }


        selectedExploreCategory =
          category;


        /*
          カテゴリを変えたら
          表示件数を50件に戻す
        */

        exploreVisibleCount =
          EXPLORE_PAGE_SIZE;


        /*
          チェックと
          EXPLORE上の表示を更新
        */

        updateCategorySheetSelection();


        /*
          検索結果を即更新
        */

        renderExplore();


        /*
          選択したら
          ボトムシートを閉じる
        */

        closeCategorySheet();

      }
    );

  }
);


/* =========================
   背景タップで閉じる
========================= */

categorySheet.addEventListener(
  "click",
  event => {

    if (
      event.target ===
      categorySheet
    ) {

      closeCategorySheet();

    }

  }
);


/* =========================
   Escapeキーでも閉じる

   PCで確認するときにも便利
========================= */

document.addEventListener(
  "keydown",
  event => {

    if (
      event.key === "Escape" &&
      !categorySheet.hidden
    ) {

      closeCategorySheet();

    }

  }
);


/* =========================
   CALENDAR画面を開く
========================= */

function showCalendarView() {

  /*
    ボトムシートが
    開いていたら閉じる
  */

  closeCategorySheet();


  currentMainView =
    "calendar";

  calendarView.hidden =
    false;

  exploreView.hidden =
    true;

  detailView.hidden =
    true;

  bottomNav.hidden =
    false;


  calendarNavButton
    .classList.add("active");

  exploreNavButton
    .classList.remove("active");


  renderCalendar();

  renderSelectedDate();

}


/* =========================
   EXPLORE画面を開く
========================= */

function showExploreView() {

  currentMainView =
    "explore";

  calendarView.hidden =
    true;

  exploreView.hidden =
    false;

  detailView.hidden =
    true;

  bottomNav.hidden =
    false;


  calendarNavButton
    .classList.remove("active");

  exploreNavButton
    .classList.add("active");


  renderExplore();

}


/* =========================
   下部ナビ
========================= */

calendarNavButton.addEventListener(
  "click",
  () => {

    showCalendarView();

    window.scrollTo({
      top: 0,
      behavior: "instant"
    });

  }
);


exploreNavButton.addEventListener(
  "click",
  () => {

    showExploreView();

    window.scrollTo({
      top: 0,
      behavior: "instant"
    });

  }
);


/* =========================
   DETAILを開く
========================= */

function openDetail(
  supply,
  fromView
) {

  currentMainView =
    fromView;


  /* 共通情報 */

  detailTitle.textContent =
    supply.title;

  detailDate.textContent =
    formatDisplayDate(
      supply.date
    );


  /* =====================
     YouTube
  ===================== */

  if (
    supply.type === "youtube"
  ) {

    const youtubeUrl =
      supply.url ||
      `https://www.youtube.com/watch?v=${supply.videoId}`;

    const thumbnailUrl =
      supply.thumbnail ||
      `https://i.ytimg.com/vi/${supply.videoId}/maxresdefault.jpg`;


    detailThumbnailWrapper.hidden =
      false;

    detailThumbnail.src =
      thumbnailUrl;

    detailThumbnail.alt =
      `${supply.title}のサムネイル`;


    detailType.innerHTML = `
      <span class="dot youtube-dot"></span>
      <span>YouTube</span>
    `;


    detailMember.hidden =
      true;

    detailMember.textContent =
      "";


    detailExternalLink.href =
      youtubeUrl;

    detailExternalLinkText.textContent =
      "YouTubeで見る";


    detailExternalLink.classList.remove(
      "fc-link"
    );

    detailExternalLink.classList.add(
      "youtube-link"
    );

  }


  /* =====================
     Member Diary
  ===================== */

  else if (
    supply.type ===
    "member_diary"
  ) {

    /*
      Member Diaryには
      サムネイルを表示しない
    */

    detailThumbnailWrapper.hidden =
      true;

    detailThumbnail.src =
      "";

    detailThumbnail.alt =
      "";


    detailType.innerHTML = `
      <span class="dot fc-dot"></span>
      <span>Member Diary</span>
    `;


    if (
      supply.member
    ) {

      detailMember.hidden =
        false;

      detailMember.textContent =
        supply.member;

    } else {

      detailMember.hidden =
        true;

      detailMember.textContent =
        "";

    }


    detailExternalLink.href =
      supply.url || "#";

    detailExternalLinkText.textContent =
      "公式サイトで見る";


    detailExternalLink.classList.remove(
      "youtube-link"
    );

    detailExternalLink.classList.add(
      "fc-link"
    );

  }

    /* =====================
     Movie
  ===================== */

  else if (
    supply.type === "movie"
  ) {

    /*
      Movieは取得済みの
      サムネイルを表示
    */

    if (supply.thumbnail) {

      detailThumbnailWrapper.hidden =
        false;

      detailThumbnail.src =
        supply.thumbnail;

      detailThumbnail.alt =
        `${supply.title}のサムネイル`;

    } else {

      detailThumbnailWrapper.hidden =
        true;

      detailThumbnail.src =
        "";

      detailThumbnail.alt =
        "";

    }


    detailType.innerHTML = `
      <span class="dot fc-dot"></span>
      <span>Movie</span>
    `;


    /*
      Movieには
      メンバー名項目なし
    */

    detailMember.hidden =
      true;

    detailMember.textContent =
      "";


    detailExternalLink.href =
      supply.url || "#";

    detailExternalLinkText.textContent =
      "公式サイトで見る";


    detailExternalLink.classList.remove(
      "youtube-link"
    );

    detailExternalLink.classList.add(
      "fc-link"
    );

  }

  /* =====================
     未知の供給種別
  ===================== */

  else {

    detailThumbnailWrapper.hidden =
      true;

    detailThumbnail.src =
      "";

    detailThumbnail.alt =
      "";

    detailType.textContent =
      supply.type || "";

    detailMember.hidden =
      true;

    detailMember.textContent =
      "";

    detailExternalLink.href =
      supply.url || "#";

    detailExternalLinkText.textContent =
      "外部サイトで見る";

    detailExternalLink.classList.remove(
      "youtube-link",
      "fc-link"
    );

  }


  /* 画面切り替え */

  calendarView.hidden =
    true;

  exploreView.hidden =
    true;

  detailView.hidden =
    false;

  bottomNav.hidden =
    true;


  /* ページ上部へ */

  window.scrollTo({
    top: 0,
    behavior: "instant"
  });

}


/* =========================
   DETAILから戻る
========================= */

function closeDetail() {

  detailView.hidden =
    true;

  bottomNav.hidden =
    false;


  if (
    currentMainView ===
    "explore"
  ) {

    calendarView.hidden =
      true;

    exploreView.hidden =
      false;

    calendarNavButton
      .classList.remove("active");

    exploreNavButton
      .classList.add("active");

  } else {

    calendarView.hidden =
      false;

    exploreView.hidden =
      true;

    calendarNavButton
      .classList.add("active");

    exploreNavButton
      .classList.remove("active");

  }

}


/* DETAIL 戻るボタン */

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

    if (
      displayMonth < 0
    ) {

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

    if (
      displayMonth > 11
    ) {

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
    INIの活動開始時期に合わせて
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
      document.createElement(
        "option"
      );

    option.value =
      year;

    option.textContent =
      `${year}年`;

    yearSelect.appendChild(
      option
    );

  }


  /* 1月〜12月 */

  for (
    let month = 1;
    month <= 12;
    month++
  ) {

    const option =
      document.createElement(
        "option"
      );

    option.value =
      month;

    option.textContent =
      `${month}月`;

    monthSelect.appendChild(
      option
    );

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

    monthPicker.hidden =
      false;

  }
);


/* =========================
   年月選択をキャンセル
========================= */

monthPickerCancel.addEventListener(
  "click",
  () => {

    monthPicker.hidden =
      true;

  }
);


/* =========================
   選択した年月へ移動
========================= */

monthPickerGo.addEventListener(
  "click",
  () => {

    const selectedYear =
      Number(
        yearSelect.value
      );

    const selectedMonth =
      Number(
        monthSelect.value
      );


    displayYear =
      selectedYear;

    displayMonth =
      selectedMonth - 1;


    monthPicker.hidden =
      true;

    renderCalendar();

  }
);


/* =========================
   背景を押したら
   年月選択を閉じる
========================= */

monthPicker.addEventListener(
  "click",
  event => {

    if (
      event.target ===
      monthPicker
    ) {

      monthPicker.hidden =
        true;

    }

  }
);


/* =========================
   初期設定
========================= */

createMonthPickerOptions();

updateCategorySheetSelection();

loadSupplies();
