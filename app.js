const $ = id => document.getElementById(id);

const calendar = $("calendar");
const currentMonth = $("currentMonth");
const selectedDate = $("selectedDate");
const supplyList = $("supplyList");
const prevMonthButton = $("prevMonth");
const nextMonthButton = $("nextMonth");
const monthPickerButton = $("monthPickerButton");
const monthPicker = $("monthPicker");
const yearSelect = $("yearSelect");
const monthSelect = $("monthSelect");
const monthPickerCancel = $("monthPickerCancel");
const monthPickerGo = $("monthPickerGo");
const calendarView = $("calendarView");
const exploreView = $("exploreView");
const detailView = $("detailView");
const bottomNav = $("bottomNav");
const calendarNavButton = $("calendarNavButton");
const exploreNavButton = $("exploreNavButton");
const exploreSearchInput = $("exploreSearchInput");
const exploreResultLabel = $("exploreResultLabel");
const exploreResultCount = $("exploreResultCount");
const exploreList = $("exploreList");
const exploreLoadMore = $("exploreLoadMore");
const exploreCategoryButton = $("exploreCategoryButton");
const exploreCategoryLabel = $("exploreCategoryLabel");
const categorySheet = $("categorySheet");
const categorySheetClose = $("categorySheetClose");
const categorySheetOptions = document.querySelectorAll(
  ".category-sheet-option"
);
const detailBackButton = $("detailBackButton");
const detailThumbnailWrapper = $("detailThumbnailWrapper");
const detailThumbnail = $("detailThumbnail");
const detailType = $("detailType");
const detailTitle = $("detailTitle");
const detailDate = $("detailDate");
const detailMember = $("detailMember");
const detailScheduleMembers = $("detailScheduleMembers");
const detailScheduleMembersText = $("detailScheduleMembersText");
const detailScheduleText = $("detailScheduleText");
const detailXMedia = $("detailXMedia");
const detailXPosts = $("detailXPosts");
const detailXPostsList = $("detailXPostsList");
const detailScheduleLinks = $("detailScheduleLinks");
const detailScheduleLinksList = $("detailScheduleLinksList");
const detailExternalLink = $("detailExternalLink");
const detailExternalLinkText = $("detailExternalLinkText");


/* ==========================================================
   データ
========================================================== */

let supplies = [];


/* ==========================================================
   カレンダー状態
========================================================== */

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

let currentMainView = "calendar";


/* ==========================================================
   EXPLORE状態
========================================================== */

const EXPLORE_PAGE_SIZE = 50;

let exploreVisibleCount =
  EXPLORE_PAGE_SIZE;

let selectedExploreCategory =
  "all";


const exploreCategoryNames = {
  all: "すべて",
  youtube: "YouTube",
  member_diary: "Member Diary",
  staff_report: "Staff Report",
  movie: "Movie",
  radio: "Radio",
  photo: "Photo",
  message: "Message",
  schedule: "Schedule",
  x: "X"
};


/* ==========================================================
   JSON読み込み
========================================================== */

async function fetchJson(path) {
  const response =
    await fetch(
      `${path}?v=${Date.now()}`,
      {
        cache: "no-store"
      }
    );


  if (!response.ok) {
    throw new Error(
      `${path} を読み込めませんでした。HTTP ${response.status}`
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


async function loadSupplyFile(
  path,
  label
) {
  try {
    const data =
      await fetchJson(path);

    console.log(
      `${label}: ${data.length}件読み込み`
    );

    return data;
  } catch (error) {
    console.error(
      `${label}の読み込みに失敗しました。`,
      error
    );

    return [];
  }
}


async function loadSupplies() {
  const [
    youtube,
    memberDiary,
    staffReport,
    movie,
    radio,
    photo,
    message,
    schedule ,
    xContents
  ] =
    await Promise.all([
      loadSupplyFile(
        "data/youtube.json",
        "YouTube"
      ),

      loadSupplyFile(
        "data/member_diary.json",
        "Member Diary"
      ),

      loadSupplyFile(
        "data/staff_report.json",
        "Staff Report"
      ),

      loadSupplyFile(
        "data/movie.json",
        "Movie"
      ),

      loadSupplyFile(
        "data/radio.json",
        "Radio"
      ),

      loadSupplyFile(
        "data/photo.json",
        "Photo"
      ),

      loadSupplyFile(
        "data/message.json",
        "Message"
      ),

      loadSupplyFile(
        "data/schedule.json",
        "Schedule"
      ),

      loadSupplyFile(
        "data/x_contents.json",
        "X Contents"
      )
    ]);



  supplies = [
    ...youtube,
    ...memberDiary,
    ...staffReport,
    ...movie,
    ...radio,
    ...photo,
    ...message,
    ...schedule,
    ...xContents
  ];


  console.log(
    `全供給データ: ${supplies.length}件`
  );


  createMonthPickerOptions();


  if (
    currentMainView === "calendar"
  ) {
    renderCalendar();
    renderSelectedDate();
  } else if (
    currentMainView === "explore"
  ) {
    renderExplore();
  }
}


/* ==========================================================
   日付
========================================================== */

function formatDateKey(
  year,
  month,
  day
) {
  return (
    `${year}-` +
    `${String(month + 1).padStart(2, "0")}-` +
    `${String(day).padStart(2, "0")}`
  );
}


function formatDisplayDate(
  dateString
) {
  if (!dateString) {
    return "";
  }


  const [
    year,
    month,
    day
  ] =
    dateString
      .split("-")
      .map(Number);


  if (
    year &&
    month &&
    day
  ) {
    return (
      `${year}年` +
      `${month}月` +
      `${day}日`
    );
  }


  return dateString;
}


/* ==========================================================
   並び順
========================================================== */

function compareSuppliesAscending(
  a,
  b
) {
  const aDate =
    String(
      a.publishedAt ||
      a.postedAt ||
      a.date ||
      ""
    );

  const bDate =
    String(
      b.publishedAt ||
      b.postedAt ||
      b.date ||
      ""
    );


  const dateComparison =
    aDate.localeCompare(
      bDate
    );


  if (
    dateComparison !== 0
  ) {
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


/* ==========================================================
   カテゴリ判定
========================================================== */

function isFcSupply(
  supply
) {
  return (
    supply.group === "fc" ||
    [
      "member_diary",
      "staff_report",
      "movie",
      "radio",
      "photo",
      "message"
    ].includes(
      supply.type
    )
  );
}


/* ==========================================================
   カレンダー
========================================================== */

function renderCalendar() {
  if (
    !calendar ||
    !currentMonth
  ) {
    return;
  }


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
    月曜日始まり。

    JS:
    日=0
    月=1
    ...
    土=6

    ↓

    月=0
    ...
    日=6
  */

  const startPosition =
    (
      firstDay.getDay() +
      6
    ) % 7;


  /*
    月初前の空白
  */

  for (
    let i = 0;
    i < startPosition;
    i++
  ) {
    const empty =
      document.createElement(
        "div"
      );

    empty.className =
      "calendar-day empty";

    calendar.appendChild(
      empty
    );
  }


  /*
    日付
  */

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


    const button =
      document.createElement(
        "button"
      );

    button.type =
      "button";

    button.className =
      "calendar-day";


    /*
      今日
    */

    if (
      displayYear ===
        today.getFullYear() &&
      displayMonth ===
        today.getMonth() &&
      day ===
        today.getDate()
    ) {
      button.classList.add(
        "today"
      );
    }


    /*
      選択日
    */

    if (
      dateKey ===
      selectedDateKey
    ) {
      button.classList.add(
        "selected"
      );
    }


    const number =
      document.createElement(
        "span"
      );

    number.className =
      "day-number";

    number.textContent =
      String(day);

    button.appendChild(
      number
    );


    /*
      この日の供給
    */

    const daySupplies =
      supplies.filter(
        supply =>
          supply.date ===
          dateKey
      );


    const hasYouTube =
      daySupplies.some(
        supply =>
          supply.type ===
          "youtube"
      );


    const hasFc =
      daySupplies.some(
        isFcSupply
      );


    const hasSchedule =
      daySupplies.some(
        supply =>
          supply.type ===
          "schedule"
      );


    const hasX =
      daySupplies.some(
        supply =>
          supply.type ===
          "x"
      );


    if (
      hasYouTube ||
      hasFc ||
      hasSchedule ||
      hasX
    ) {
      const dots =
        document.createElement(
          "div"
        );

      dots.className =
        "supply-dots";


      if (hasYouTube) {
        const dot =
          document.createElement(
            "span"
          );

        dot.className =
          "dot youtube-dot";

        dots.appendChild(
          dot
        );
      }


      if (hasFc) {
        const dot =
          document.createElement(
            "span"
          );

        dot.className =
          "dot fc-dot";

        dots.appendChild(
          dot
        );
      }


      if (hasSchedule) {
        const dot =
          document.createElement(
            "span"
          );

        dot.className =
          "dot schedule-dot";

        dots.appendChild(
          dot
        );
      }


      if (hasX) {
        const dot =
          document.createElement(
            "span"
          );

        dot.className =
          "dot x-dot";

        dots.appendChild(
          dot
        );
      }


      button.appendChild(
        dots
      );
    }


    button.addEventListener(
      "click",
      () => {
        selectedDateKey =
          dateKey;

        renderCalendar();
        renderSelectedDate();
      }
    );


    calendar.appendChild(
      button
    );
  }
}


/* ==========================================================
   メンバー表示
========================================================== */

function getMemberText(
  supply
) {
  if (
    Array.isArray(
      supply.members
    ) &&
    supply.members.length > 0
  ) {
    return supply.members.join(
      "・"
    );
  }


  return (
    supply.member ||
    ""
  );
}


/* ==========================================================
   選択日の供給
========================================================== */

function createSupplyItem(
  supply,
  fromView,
  showMember = false
) {
  const item =
    document.createElement(
      "button"
    );

  item.type =
    "button";

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
    supply.title || "";


  text.appendChild(
    title
  );


  const memberText =
    getMemberText(
      supply
    );


  if (
    (
      showMember ||
      supply.type ===
        "schedule" ||
      supply.type ===
        "x"
    ) &&
    memberText
  ) {
    const member =
      document.createElement(
        "span"
      );

    member.className =
      "supply-member";

    member.textContent =
      memberText;

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


function appendSupplyCategory(
  title,
  categorySupplies,
  showMember = false
) {
  if (
    categorySupplies.length === 0
  ) {
    return;
  }


  const category =
    document.createElement(
      "div"
    );

  category.className =
    "supply-category";


  const categoryTitle =
    document.createElement(
      "div"
    );

  categoryTitle.className =
    "supply-category-title";


  let dotClass =
    "fc-dot";


  if (
    title === "YouTube"
  ) {
    dotClass =
      "youtube-dot";
  } else if (
    title === "Schedule"
  ) {
    dotClass =
      "schedule-dot";
  } else if (
    title === "X"
  ) {
    dotClass =
      "x-dot";
  }


  categoryTitle.innerHTML = `
    <span class="dot ${dotClass}"></span>
    <span>${title}</span>
  `;


  category.appendChild(
    categoryTitle
  );


  categorySupplies.forEach(
    supply => {
      category.appendChild(
        createSupplyItem(
          supply,
          "calendar",
          showMember
        )
      );
    }
  );


  supplyList.appendChild(
    category
  );
}


function renderSelectedDate() {
  if (
    !selectedDate ||
    !supplyList
  ) {
    return;
  }


  selectedDate.textContent =
    formatDisplayDate(
      selectedDateKey
    );


  const selected =
    supplies
      .filter(
        supply =>
          supply.date ===
          selectedDateKey
      )
      .sort(
        compareSuppliesAscending
      );


  supplyList.innerHTML =
    "";


  if (
    selected.length === 0
  ) {
    supplyList.innerHTML = `
      <p class="no-supplies">
        この日の供給はありません。
      </p>
    `;

    return;
  }


  appendSupplyCategory(
    "YouTube",
    selected.filter(
      supply =>
        supply.type ===
        "youtube"
    )
  );


  appendSupplyCategory(
    "Member Diary",
    selected.filter(
      supply =>
        supply.type ===
        "member_diary"
    ),
    true
  );


  appendSupplyCategory(
    "Staff Report",
    selected.filter(
      supply => supply.type === "staff_report"
    ),
    true
  );

  appendSupplyCategory(
    "Movie",
    selected.filter(
      supply =>
        supply.type ===
        "movie"
    )
  );


  appendSupplyCategory(
    "Radio",
    selected.filter(
      supply =>
        supply.type ===
        "radio"
    )
  );


  appendSupplyCategory(
    "Photo",
    selected.filter(
      supply =>
        supply.type ===
        "photo"
    )
  );


  appendSupplyCategory(
    "Message",
    selected.filter(
      supply =>
        supply.type ===
        "message"
    )
  );


  appendSupplyCategory(
    "Schedule",
    selected.filter(
      supply =>
        supply.type ===
        "schedule"
    )
  );


  appendSupplyCategory(
    "X",
    selected.filter(
      supply =>
        supply.type ===
        "x"
    ),
    true
  );
}


/* ==========================================================
   EXPLORE
========================================================== */

function matchesExploreCategory(
  supply
) {
  return (
    selectedExploreCategory ===
      "all" ||
    supply.type ===
      selectedExploreCategory
  );
}


function getExploreSupplies() {
  const rawQuery =
    exploreSearchInput
      .value
      .trim()
      .toLocaleLowerCase();


  const sorted =
    [...supplies]
      .sort(
        (a, b) => {
          const aDate =
            String(
              a.publishedAt ||
              a.postedAt ||
              a.date ||
              ""
            );

          const bDate =
            String(
              b.publishedAt ||
              b.postedAt ||
              b.date ||
              ""
            );


          const comparison =
            bDate.localeCompare(
              aDate
            );


          if (
            comparison !== 0
          ) {
            return comparison;
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
      )
      .filter(
        matchesExploreCategory
      );


  if (!rawQuery) {
    return sorted;
  }


  const keywords =
    rawQuery
      .split(/\s+/)
      .filter(Boolean);


  return sorted.filter(
    supply => {
      const fields = [
        supply.title,
        supply.member,
        supply.categoryLabel,
        supply.text,
        ...(
          Array.isArray(
            supply.members
          )
            ? supply.members
            : []
        )
      ]
        .filter(Boolean)
        .join(" ")
        .toLocaleLowerCase();


      return keywords.every(
        keyword =>
          fields.includes(
            keyword
          )
      );
    }
  );
}


function setExploreItemCategory(
  category,
  supply
) {
  if (
    supply.type ===
    "youtube"
  ) {
    category.innerHTML = `
      <span class="dot youtube-dot"></span>
      <span>YouTube</span>
    `;

    return;
  }


  if (
    supply.type ===
    "schedule"
  ) {
    const label =
      supply.categoryLabel
        ? `Schedule / ${supply.categoryLabel}`
        : "Schedule";


    category.innerHTML = `
      <span class="dot schedule-dot"></span>
      <span>${label}</span>
    `;

    return;
  }


  if (
    supply.type ===
    "x"
  ) {
    category.innerHTML = `
      <span class="dot x-dot"></span>
      <span>X</span>
    `;

    return;
  }


  const names = {
    member_diary:
      "Member Diary",

    staff_report:
      "Staff Report",

    movie:
      "Movie",

    radio:
      "Radio",

    photo:
      "Photo",

    message:
      "Message"
  };


  if (
    names[supply.type]
  ) {
    category.innerHTML = `
      <span class="dot fc-dot"></span>
      <span>${names[supply.type]}</span>
    `;

    return;
  }


  category.textContent =
    supply.type || "";
}


function renderExplore() {
  if (
    !exploreSearchInput ||
    !exploreList
  ) {
    return;
  }


  const query =
    exploreSearchInput
      .value
      .trim();


  const filtered =
    getExploreSupplies();


  if (query) {
    exploreResultLabel.textContent =
      "SEARCH RESULTS";
  } else if (
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


  exploreResultCount.textContent =
    `${filtered.length.toLocaleString()}件`;


  exploreList.innerHTML =
    "";


  if (
    filtered.length === 0
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


  filtered
    .slice(
      0,
      exploreVisibleCount
    )
    .forEach(
      supply => {
        const item =
          document.createElement(
            "button"
          );

        item.type =
          "button";

        item.className =
          "explore-item";


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


        const category =
          document.createElement(
            "span"
          );

        category.className =
          "explore-item-category";


        setExploreItemCategory(
          category,
          supply
        );


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
          supply.title || "";


        text.appendChild(
          title
        );


        const memberText =
          getMemberText(
            supply
          );


        if (
          memberText &&
          [
            "member_diary",
            "schedule",
            "x"
          ].includes(
            supply.type
          )
        ) {
          const member =
            document.createElement(
              "span"
            );

          member.className =
            "explore-item-member";

          member.textContent =
            memberText;

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


  exploreLoadMore.hidden =
    exploreVisibleCount >=
    filtered.length;
}


/* ==========================================================
   EXPLOREカテゴリ選択
========================================================== */

function openCategorySheet() {
  categorySheet.hidden =
    false;

  exploreCategoryButton.setAttribute(
    "aria-expanded",
    "true"
  );

  updateCategorySheetSelection();
}


function closeCategorySheet() {
  categorySheet.hidden =
    true;

  exploreCategoryButton.setAttribute(
    "aria-expanded",
    "false"
  );
}


function updateCategorySheetSelection() {
  categorySheetOptions.forEach(
    option => {
      const selected =
        option.dataset.category ===
        selectedExploreCategory;


      option.classList.toggle(
        "selected",
        selected
      );


      const check =
        option.querySelector(
          ".category-sheet-check"
        );


      if (check) {
        check.textContent =
          selected
            ? "✓"
            : "";
      }
    }
  );


  exploreCategoryLabel.textContent =
    exploreCategoryNames[
      selectedExploreCategory
    ] || "すべて";
}


/* ==========================================================
   メイン画面切り替え
========================================================== */

function showCalendarView() {
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


  calendarNavButton.classList.add(
    "active"
  );

  exploreNavButton.classList.remove(
    "active"
  );


  renderCalendar();
  renderSelectedDate();
}


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


  calendarNavButton.classList.remove(
    "active"
  );

  exploreNavButton.classList.add(
    "active"
  );


  renderExplore();
}


/* ==========================================================
   DETAIL初期化
========================================================== */

function resetDetail() {
  detailThumbnailWrapper.hidden =
    true;

  detailThumbnail.src =
    "";

  detailThumbnail.alt =
    "";


  detailType.innerHTML =
    "";


  detailMember.hidden =
    true;

  detailMember.textContent =
    "";


  detailScheduleMembers.hidden =
    true;

  detailScheduleMembersText.textContent =
    "";


  detailScheduleText.hidden =
    true;

  detailScheduleText.textContent =
    "";


  detailXMedia.hidden =
    true;

  detailXMedia.innerHTML =
    "";


  detailXPosts.hidden =
    true;

  detailXPostsList.innerHTML =
    "";


  detailScheduleLinks.hidden =
    true;

  detailScheduleLinksList.innerHTML =
    "";


  detailExternalLink.classList.remove(
    "youtube-link",
    "fc-link",
    "schedule-link",
    "x-link"
  );


  detailExternalLink.hidden =
    false;

  detailExternalLink.href =
    "#";
}


/* ==========================================================
   FC DETAIL
========================================================== */

function setFcDetail(
  supply,
  typeName
) {
  if (supply.thumbnail) {
    detailThumbnailWrapper.hidden =
      false;

    detailThumbnail.src =
      supply.thumbnail;

    detailThumbnail.alt =
      `${supply.title}のサムネイル`;
  }


  detailType.innerHTML = `
    <span class="dot fc-dot"></span>
    <span>${typeName}</span>
  `;


  detailExternalLink.href =
    supply.url || "#";


  detailExternalLinkText.textContent =
    "公式サイトで見る";


  detailExternalLink.classList.add(
    "fc-link"
  );
}


/* ==========================================================
   X投稿
========================================================== */

function normalizeXPosts(
  posts
) {
  if (
    !Array.isArray(posts)
  ) {
    return [];
  }


  const seen =
    new Set();


  return posts
    .map(
      post => {
        if (
          typeof post ===
          "string"
        ) {
          return {
            url: post
          };
        }


        return post || {};
      }
    )
    .filter(
      post => {
        const url =
          String(
            post.url || ""
          ).trim();


        if (
          !url ||
          seen.has(url)
        ) {
          return false;
        }


        seen.add(url);

        return true;
      }
    );
}


/* ==========================================================
   X メディア表示
========================================================== */

function renderXMedia(
  media,
  container,
  postUrl
) {
  if (
    !container ||
    !Array.isArray(media)
  ) {
    return false;
  }

  const validMedia =
    media.filter(
      item =>
        item &&
        (
          (
            item.type === "photo" &&
            item.url
          ) ||
          (
            item.type === "video" &&
            item.thumbnailUrl
          )
        )
    );

  if (validMedia.length === 0) {
    return false;
  }

  container.innerHTML = "";
  container.classList.toggle(
    "single",
    validMedia.length === 1
  );

  validMedia.forEach(
    item => {
      if (item.type === "photo") {
        const image =
          document.createElement("img");

        image.className =
          "detail-x-media-image";
        image.src = item.url;
        image.alt = "X投稿の画像";
        image.loading = "lazy";

        container.appendChild(image);
        return;
      }

      const image =
        document.createElement("img");

      image.className =
        "detail-x-media-image";
      image.src = item.thumbnailUrl;
      image.alt = "X投稿の動画サムネイル";
      image.loading = "lazy";

      const link =
        document.createElement("a");

      link.href = postUrl;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.setAttribute(
        "aria-label",
        "Xの動画投稿を開く"
      );

      link.appendChild(image);
      container.appendChild(link);
    }
  );

  container.hidden = false;
  return true;
}


/* ==========================================================
   関連X投稿取得
========================================================== */

/* ==========================================================
   X POSTS表示
========================================================== */

function renderXPosts(
  supply
) {
  detailXPosts.hidden =
    true;

  detailXPostsList.innerHTML =
    "";


  const posts =
    normalizeXPosts(
      supply.posts
    );


  if (
    posts.length === 0
  ) {
    return;
  }


  posts.forEach(
    post => {
      const anchor =
        document.createElement(
          "a"
        );

      const card =
        document.createElement(
          "div"
        );

      card.className =
        "detail-x-post-card";


      const media =
        document.createElement(
          "div"
        );

      media.className =
        "detail-x-post-media";

      renderXMedia(
        post.media,
        media,
        post.url
      );


      anchor.className =
        "detail-x-post-link";

      anchor.href =
        post.url;

      anchor.target =
        "_blank";

      anchor.rel =
        "noopener noreferrer";


      const text =
        document.createElement(
          "span"
        );

      text.className =
        "detail-x-post-link-text";


      if (post.text) {
        /*
          Xの取得データ末尾に含まれる
          メディア用t.co URLは表示しない。
          元データ自体は変更しない。
        */
        text.textContent =
          String(
            post.text
          )
            .replace(
              /[ \t]+https:\/\/t\.co\/[A-Za-z0-9]+\s*$/u,
              ""
            )
            .trim();
      } else {
        text.textContent =
          "Xで見る";
      }


      const arrow =
        document.createElement(
          "span"
        );

      arrow.className =
        "detail-x-post-arrow";

      arrow.textContent =
        "↗";


      anchor.appendChild(
        text
      );

      anchor.appendChild(
        arrow
      );


      card.appendChild(
        media
      );

      card.appendChild(
        anchor
      );

      detailXPostsList.appendChild(
        card
      );
    }
  );


  detailXPosts.hidden =
    false;
}


/* ==========================================================
   Schedule DETAIL
========================================================== */

function setScheduleDetail(
  supply
) {
  /*
    X由来Scheduleも
    通常Scheduleと同じ黄色で表示する。
  */

  const scheduleType =
    supply.categoryLabel
      ? `Schedule / ${supply.categoryLabel}`
      : "Schedule";


  detailType.innerHTML = `
    <span class="dot schedule-dot"></span>
    <span>${scheduleType}</span>
  `;


  /*
    出演メンバー
  */

  if (
    Array.isArray(
      supply.members
    ) &&
    supply.members.length > 0
  ) {
    detailScheduleMembers.hidden =
      false;

    detailScheduleMembersText.textContent =
      supply.members.join(
        "・"
      );
  }


  /*
    詳細本文
  */

  const body =
    String(
      supply.detailText || ""
    ).trim();


  if (body) {
    detailScheduleText.hidden =
      false;

    detailScheduleText.textContent =
      body;
  }



  /*
    関連リンク
  */

  const externalLinks =
    Array.isArray(
      supply.externalLinks
    )
      ? supply.externalLinks
      : [];


  externalLinks.forEach(
    link => {
      if (
        !link ||
        !link.url
      ) {
        return;
      }


      const anchor =
        document.createElement(
          "a"
        );

      anchor.className =
        "detail-schedule-link";

      anchor.href =
        link.url;

      anchor.target =
        "_blank";

      anchor.rel =
        "noopener noreferrer";


      const text =
        document.createElement(
          "span"
        );

      text.className =
        "detail-schedule-link-text";

      text.textContent =
        String(
          link.label ||
          link.url
        );


      const arrow =
        document.createElement(
          "span"
        );

      arrow.className =
        "detail-schedule-link-arrow";

      arrow.textContent =
        "↗";


      anchor.appendChild(
        text
      );

      anchor.appendChild(
        arrow
      );


      detailScheduleLinksList.appendChild(
        anchor
      );
    }
  );


  detailScheduleLinks.hidden =
    detailScheduleLinksList
      .children
      .length === 0;


  /*
    公式Scheduleの場合は
    INI公式サイトへのリンク。

    X由来Scheduleでurlがある場合は
    関連ページとして表示。
  */

  if (supply.url) {
    detailExternalLink.href =
      supply.url;


    if (
      supply.source ===
      "x"
    ) {
      detailExternalLinkText.textContent =
        "関連ページを見る";
    } else {
      detailExternalLinkText.textContent =
        "INI公式サイトで見る";
    }


    detailExternalLink.classList.add(
      "schedule-link"
    );
  } else {
    detailExternalLink.hidden =
      true;
  }
}


/* ==========================================================
   X独自コンテンツ DETAIL
========================================================== */

function setXDetail(
  supply
) {
  detailType.innerHTML = `
    <span class="dot x-dot"></span>
    <span>X</span>
  `;


  const memberText =
    getMemberText(
      supply
    );


  if (memberText) {
    detailMember.hidden =
      false;

    detailMember.textContent =
      memberText;
  }


  /*
    X供給は1件以上のpostsを持つ。
    単独投稿も同じUIで表示する。
  */

  renderXPosts(
    supply
  );


  /*
    供給単位の外部リンクは持たない。
    各投稿カードからXへ移動する。
  */

  detailExternalLink.hidden =
    true;
}


/* ==========================================================
   DETAIL
========================================================== */

function openDetail(
  supply,
  fromView
) {
  currentMainView =
    fromView;


  /*
    前のDETAIL表示を
    必ず初期化する。
  */

  resetDetail();


  detailTitle.textContent =
    supply.title || "";


  detailDate.textContent =
    formatDisplayDate(
      supply.date
    );


  /* YouTube */

  if (
    supply.type ===
    "youtube"
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


    detailExternalLink.href =
      youtubeUrl;

    detailExternalLinkText.textContent =
      "YouTubeで見る";

    detailExternalLink.classList.add(
      "youtube-link"
    );

  }


  /* Member Diary */

  else if (
    supply.type ===
    "member_diary"
  ) {
    detailType.innerHTML = `
      <span class="dot fc-dot"></span>
      <span>Member Diary</span>
    `;


    if (supply.member) {
      detailMember.hidden =
        false;

      detailMember.textContent =
        supply.member;
    }


    detailExternalLink.href =
      supply.url || "#";

    detailExternalLinkText.textContent =
      "公式サイトで見る";

    detailExternalLink.classList.add(
      "fc-link"
    );

  }


  /* Staff Report */

  else if (
    supply.type === "staff_report"
  ) {
    detailType.innerHTML = `
      <span class="dot fc-dot"></span>
      <span>Staff Report</span>
    `;
    detailExternalLink.href = supply.url || "#";
    detailExternalLinkText.textContent = "公式サイトで見る";
    detailExternalLink.classList.add("fc-link");
  }

  /* FC Contents */

  else if (
    [
      "movie",
      "radio",
      "photo",
      "message"
    ].includes(
      supply.type
    )
  ) {
    const names = {
      movie:
        "Movie",

      radio:
        "Radio",

      photo:
        "Photo",

      message:
        "Message"
    };


    setFcDetail(
      supply,
      names[supply.type]
    );

  }


  /* Schedule */

  else if (
    supply.type ===
    "schedule"
  ) {
    setScheduleDetail(
      supply
    );
  }


  /* X */

  else if (
    supply.type ===
    "x"
  ) {
    setXDetail(
      supply
    );
  }


  /* 未知の種別 */

  else {
    detailType.textContent =
      supply.type || "";


    detailExternalLink.href =
      supply.url || "#";

    detailExternalLinkText.textContent =
      "外部サイトで見る";

  }


  calendarView.hidden =
    true;

  exploreView.hidden =
    true;

  detailView.hidden =
    false;

  bottomNav.hidden =
    true;


  window.scrollTo({
    top: 0,
    behavior: "auto"
  });
}


/* ==========================================================
   DETAILから戻る
========================================================== */

function closeDetail() {
  detailView.hidden =
    true;

  bottomNav.hidden =
    false;


  if (
    currentMainView ===
    "explore"
  ) {
    showExploreView();
  } else {
    showCalendarView();
  }
}


/* ==========================================================
   年月選択
========================================================== */

function getLatestDataYear() {
  let latestYear =
    today.getFullYear();


  supplies.forEach(
    supply => {
      const match =
        String(
          supply.date || ""
        ).match(
          /^(\d{4})-\d{2}-\d{2}$/
        );


      if (match) {
        latestYear =
          Math.max(
            latestYear,
            Number(match[1])
          );
      }
    }
  );


  return latestYear;
}


function createMonthPickerOptions() {
  if (
    !yearSelect ||
    !monthSelect
  ) {
    return;
  }


  yearSelect.innerHTML =
    "";

  monthSelect.innerHTML =
    "";


  /*
    2021年から
    データ上の最新年まで。
  */

  for (
    let year =
      getLatestDataYear();
    year >= 2021;
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


  yearSelect.value =
    String(
      displayYear
    );

  monthSelect.value =
    String(
      displayMonth + 1
    );
}


/* ==========================================================
   EXPLOREイベント
========================================================== */

exploreSearchInput.addEventListener(
  "input",
  () => {
    exploreVisibleCount =
      EXPLORE_PAGE_SIZE;

    renderExplore();
  }
);


exploreLoadMore.addEventListener(
  "click",
  () => {
    exploreVisibleCount +=
      EXPLORE_PAGE_SIZE;

    renderExplore();
  }
);


exploreCategoryButton.addEventListener(
  "click",
  openCategorySheet
);


categorySheetClose.addEventListener(
  "click",
  closeCategorySheet
);


categorySheetOptions.forEach(
  option => {
    option.addEventListener(
      "click",
      () => {
        if (
          !option.dataset.category
        ) {
          return;
        }


        selectedExploreCategory =
          option.dataset.category;


        exploreVisibleCount =
          EXPLORE_PAGE_SIZE;


        updateCategorySheetSelection();

        renderExplore();

        closeCategorySheet();
      }
    );
  }
);


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


document.addEventListener(
  "keydown",
  event => {
    if (
      event.key ===
        "Escape" &&
      !categorySheet.hidden
    ) {
      closeCategorySheet();
    }
  }
);


/* ==========================================================
   下部ナビ
========================================================== */

calendarNavButton.addEventListener(
  "click",
  () => {
    showCalendarView();

    window.scrollTo({
      top: 0,
      behavior: "auto"
    });
  }
);


exploreNavButton.addEventListener(
  "click",
  () => {
    showExploreView();

    window.scrollTo({
      top: 0,
      behavior: "auto"
    });
  }
);


/* ==========================================================
   DETAILイベント
========================================================== */

detailBackButton.addEventListener(
  "click",
  closeDetail
);


/* ==========================================================
   月移動
========================================================== */

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


/* ==========================================================
   年月選択イベント
========================================================== */

monthPickerButton.addEventListener(
  "click",
  () => {
    createMonthPickerOptions();

    monthPicker.hidden =
      false;
  }
);


monthPickerCancel.addEventListener(
  "click",
  () => {
    monthPicker.hidden =
      true;
  }
);


monthPickerGo.addEventListener(
  "click",
  () => {
    displayYear =
      Number(
        yearSelect.value
      );

    displayMonth =
      Number(
        monthSelect.value
      ) - 1;


    monthPicker.hidden =
      true;


    renderCalendar();
  }
);


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


/* ==========================================================
   初期化
========================================================== */

let appInitialized =
  false;


function initializeApp() {
  if (
    appInitialized
  ) {
    return;
  }


  appInitialized =
    true;


  console.log(
    "INI Supply Archive 初期化開始"
  );


  createMonthPickerOptions();

  updateCategorySheetSelection();

  showCalendarView();


  console.log(
    "初期カレンダー描画完了"
  );


  loadSupplies();
}


/*
  index.htmlのscriptが
  body末尾にある場合は
  通常すでにDOMが完成している。

  Safari等も考慮して
  readyStateを確認する。
*/

if (
  document.readyState ===
  "loading"
) {
  document.addEventListener(
    "DOMContentLoaded",
    initializeApp,
    {
      once: true
    }
  );
} else {
  initializeApp();
}


/*
  iPhone Safariの
  bfcache復元対策。
*/

window.addEventListener(
  "pageshow",
  () => {
    if (
      currentMainView ===
        "calendar" &&
      !calendarView.hidden
    ) {
      renderCalendar();
      renderSelectedDate();
    }
  }
);
