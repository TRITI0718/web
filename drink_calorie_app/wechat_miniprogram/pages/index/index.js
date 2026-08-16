const allDrinks = require("../../data/drinks")

const PAGE_SIZE = 40
const COLOR_STOPS = [
  [158, 220, 245],
  [67, 160, 71],
  [156, 204, 101],
  [244, 208, 63],
  [243, 156, 18],
  [231, 76, 60],
  [139, 30, 30],
]

const SOURCE_LABELS = {
  official: "官方数据",
  third_party: "第三方数据",
  social_media: "社交媒体整理",
}

function interpolateColor(value, maximum) {
  const ratio = maximum > 0 ? Math.max(0, Math.min(1, value / maximum)) : 0
  const scaled = ratio * (COLOR_STOPS.length - 1)
  const index = Math.min(Math.floor(scaled), COLOR_STOPS.length - 2)
  const factor = scaled - index
  const start = COLOR_STOPS[index]
  const end = COLOR_STOPS[index + 1]
  const rgb = start.map((channel, i) => Math.round(channel + (end[i] - channel) * factor))
  return rgb
}

function rgba(rgb, alpha) {
  return `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${alpha})`
}

function numberText(value, unit) {
  return value === null || value === undefined ? "" : `${Number(value).toFixed(1).replace(/\.0$/, "")}${unit}`
}

Page({
  data: {
    keyword: "",
    brands: ["全部"],
    selectedBrand: "全部",
    categories: ["全部"],
    categoryIndex: 0,
    sources: ["全部", "官方数据", "第三方数据", "社交媒体数据"],
    sourceIndex: 0,
    sortOptions: ["由低到高", "由高到低"],
    sortIndex: 0,
    ranges: [
      { label: "全部", min: null, max: null },
      { label: "0–100千卡", min: 0, max: 100 },
      { label: "100–200千卡", min: 100, max: 200 },
      { label: "200–300千卡", min: 200, max: 300 },
      { label: "300千卡以上", min: 300, max: null },
    ],
    rangeIndex: 0,
    visibleDrinks: [],
    filteredDrinks: [],
    displayLimit: PAGE_SIZE,
    hasMore: false,
    stats: { count: 0, average: 0, maximum: 0 },
  },

  onLoad() {
    const brands = ["全部", ...Array.from(new Set(allDrinks.map((item) => item.brand))).sort()]
    const categories = ["全部", ...Array.from(new Set(allDrinks.map((item) => item.category).filter(Boolean))).sort()]
    this.setData({ brands, categories })
    this.applyFilters()
  },

  onSearchInput(event) {
    this.setData({ keyword: event.detail.value, displayLimit: PAGE_SIZE })
    this.applyFilters()
  },

  onBrandTap(event) {
    this.setData({ selectedBrand: event.currentTarget.dataset.value, displayLimit: PAGE_SIZE })
    this.applyFilters()
  },

  onCategoryChange(event) {
    this.setData({ categoryIndex: Number(event.detail.value), displayLimit: PAGE_SIZE })
    this.applyFilters()
  },

  onSourceChange(event) {
    this.setData({ sourceIndex: Number(event.detail.value), displayLimit: PAGE_SIZE })
    this.applyFilters()
  },

  onSortChange(event) {
    this.setData({ sortIndex: Number(event.detail.value), displayLimit: PAGE_SIZE })
    this.applyFilters()
  },

  onRangeTap(event) {
    this.setData({ rangeIndex: Number(event.currentTarget.dataset.index), displayLimit: PAGE_SIZE })
    this.applyFilters()
  },

  loadMore() {
    this.setData({ displayLimit: this.data.displayLimit + PAGE_SIZE })
    this.updateVisible()
  },

  applyFilters() {
    const keyword = this.data.keyword.trim().toLowerCase()
    const category = this.data.categories[this.data.categoryIndex]
    const sourceLabel = this.data.sources[this.data.sourceIndex]
    const range = this.data.ranges[this.data.rangeIndex]

    let filtered = allDrinks.filter((item) => {
      if (this.data.selectedBrand !== "全部" && item.brand !== this.data.selectedBrand) return false
      if (category !== "全部" && item.category !== category) return false
      if (sourceLabel !== "全部") {
        const expected = sourceLabel === "官方数据" ? "official" : sourceLabel === "第三方数据" ? "third_party" : "social_media"
        if (item.sourceType !== expected) return false
      }
      if (range.min !== null && item.calories < range.min) return false
      if (range.max !== null && item.calories > range.max) return false
      if (keyword) {
        const haystack = `${item.brand} ${item.name} ${item.nameCn} ${item.category}`.toLowerCase()
        if (!haystack.includes(keyword)) return false
      }
      return true
    })

    filtered.sort((a, b) => this.data.sortIndex === 0 ? a.calories - b.calories : b.calories - a.calories)
    const values = filtered.map((item) => item.calories)
    const maximum = values.length ? Math.max(...values) : 0
    const average = values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0
    const colored = filtered.map((item) => {
      const rgb = interpolateColor(item.calories, 576)
      const sugarText = numberText(item.sugar, "克")
      const fatText = numberText(item.fat, "克")
      const proteinText = numberText(item.protein, "克")
      const caffeineText = numberText(item.caffeine, "毫克")
      return {
        ...item,
        displayName: item.nameCn || item.name,
        meta: [item.brand, item.category, item.size].filter(Boolean).join(" · "),
        caloriesText: Number(item.calories).toFixed(1).replace(/\.0$/, ""),
        color: rgba(rgb, 1),
        colorBottom: rgba(rgb, 0.34),
        colorMiddle: rgba(rgb, 0.15),
        sugarText,
        fatText,
        proteinText,
        caffeineText,
        hasNutrition: Boolean(sugarText || fatText || proteinText || caffeineText),
        sourceLabel: SOURCE_LABELS[item.sourceType] || "来源未分类",
      }
    })

    this.setData({
      filteredDrinks: colored,
      stats: {
        count: colored.length,
        average: average.toFixed(1),
        maximum: Number(maximum).toFixed(1).replace(/\.0$/, ""),
      },
    })
    this.updateVisible()
  },

  updateVisible() {
    const visibleDrinks = this.data.filteredDrinks.slice(0, this.data.displayLimit)
    this.setData({
      visibleDrinks,
      hasMore: visibleDrinks.length < this.data.filteredDrinks.length,
    })
  },
})
