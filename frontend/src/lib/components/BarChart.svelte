<script>
  export let data = []
  export let title = ''
  export let color = '#6366f1'
  export let colorEnd = '#818cf8'
  export let height = 220
  export let labelKey = 'year'
  export let valueKey = 'count'
  export let emptyYears = []

  const PADDING = { top: 20, right: 16, bottom: 36, left: 44 }

  $: chartData = emptyYears.length > 0
    ? emptyYears.map(y => {
        const found = data.find(d => d[labelKey] === y)
        return { label: y, value: found ? found[valueKey] : 0 }
      })
    : data.map(d => ({ label: d[labelKey], value: d[valueKey] }))

  $: maxVal = Math.max(...chartData.map(d => d.value), 1)
  $: innerW = 600
  $: innerH = height - PADDING.top - PADDING.bottom
  $: barW = chartData.length > 0 ? (innerW - PADDING.left - PADDING.right) / chartData.length : 0
  $: barPad = barW * 0.25

  function barHeight(v) {
    return (v / maxVal) * innerH
  }

  function barX(i) {
    return PADDING.left + i * barW + barPad / 2
  }

  function barY(v) {
    return PADDING.top + innerH - barHeight(v)
  }

  function yTick(ratio) {
    return PADDING.top + innerH - ratio * innerH
  }

  $: yTicks = [0, 0.25, 0.5, 0.75, 1].map(r => ({
    y: yTick(r),
    label: Math.round(maxVal * r),
  }))

  let hoveredIdx = -1
</script>

<div class="glass-card p-6 animate-slide-up">
  {#if title}
    <h3 class="font-bold text-slate-800 dark:text-white mb-4 flex items-center gap-2">
      <span>📊</span> {title}
    </h3>
  {/if}

  <div class="w-full overflow-x-auto">
    <svg
      viewBox="0 0 {innerW} {height}"
      class="w-full"
      style="min-width: 320px; height: {height}px;"
      role="img"
      aria-label={title}
    >
      <defs>
        <linearGradient id="barGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color={color} stop-opacity="1" />
          <stop offset="100%" stop-color={colorEnd} stop-opacity="0.7" />
        </linearGradient>
        <linearGradient id="barGradHover" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color={color} stop-opacity="1" />
          <stop offset="100%" stop-color={color} stop-opacity="0.9" />
        </linearGradient>
      </defs>

      {#each yTicks as tick}
        <line
          x1={PADDING.left}
          y1={tick.y}
          x2={innerW - PADDING.right}
          y2={tick.y}
          stroke="currentColor"
          stroke-opacity="0.08"
          stroke-width="1"
          stroke-dasharray="4 4"
        />
        <text
          x={PADDING.left - 8}
          y={tick.y + 4}
          text-anchor="end"
          class="fill-slate-400 dark:fill-slate-500"
          font-size="10"
        >{tick.label}</text>
      {/each}

      <line
        x1={PADDING.left}
        y1={PADDING.top}
        x2={PADDING.left}
        y2={PADDING.top + innerH}
        stroke="currentColor"
        stroke-opacity="0.15"
        stroke-width="1"
      />
      <line
        x1={PADDING.left}
        y1={PADDING.top + innerH}
        x2={innerW - PADDING.right}
        y2={PADDING.top + innerH}
        stroke="currentColor"
        stroke-opacity="0.15"
        stroke-width="1"
      />

      {#each chartData as item, i}
        {@const bh = barHeight(item.value)}
        {@const bx = barX(i)}
        {@const by = barY(item.value)}
        {@const bw = barW - barPad}
        {@const isHovered = hoveredIdx === i}

        <rect
          x={bx}
          y={by}
          width={bw}
          height={bh > 0 ? bh : 2}
          rx="4"
          ry="4"
          fill={isHovered ? 'url(#barGradHover)' : 'url(#barGrad)'}
          opacity={item.value === 0 ? 0.25 : isHovered ? 1 : 0.85}
          class="transition-all duration-150 cursor-pointer"
          on:mouseenter={() => hoveredIdx = i}
          on:mouseleave={() => hoveredIdx = -1}
        />

        {#if isHovered && item.value > 0}
          <rect
            x={bx - 4}
            y={by - 24}
            width={bw + 8}
            height={20}
            rx="4"
            fill={color}
            opacity="0.9"
          />
          <text
            x={bx + bw / 2}
            y={by - 10}
            text-anchor="middle"
            fill="white"
            font-size="10"
            font-weight="600"
          >{item.value}</text>
        {/if}

        <text
          x={bx + bw / 2}
          y={PADDING.top + innerH + 20}
          text-anchor="middle"
          class="fill-slate-500 dark:fill-slate-400"
          font-size="10"
          font-weight={isHovered ? '700' : '400'}
        >{item.label}</text>
      {/each}
    </svg>
  </div>

  {#if chartData.every(d => d.value === 0)}
    <p class="text-center text-xs text-slate-400 dark:text-slate-500 mt-2 italic">
      Belum ada data — jalankan scraper untuk mengisi grafik
    </p>
  {:else}
    <div class="flex items-center justify-end gap-4 mt-3">
      <div class="flex items-center gap-1.5">
        <span class="w-3 h-3 rounded-sm" style="background:{color}"></span>
        <span class="text-xs text-slate-500 dark:text-slate-400">Artikel per Tahun</span>
      </div>
    </div>
  {/if}
</div>
