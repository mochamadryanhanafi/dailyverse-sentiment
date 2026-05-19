<script>
  // series: [{ name: 'Positif', data: [{year: 2015, count: 10}, ...], color: '#10b981' }, ...]
  export let series = []
  export let title = ''
  export let height = 220
  export let labelKey = 'year'
  export let valueKey = 'count'
  export let emptyYears = []

  const PADDING = { top: 20, right: 16, bottom: 36, left: 44 }

  $: maxVal = Math.max(
    ...series.flatMap(s => s.data.map(d => d[valueKey])),
    1
  )
  
  $: innerW = 600
  $: innerH = height - PADDING.top - PADDING.bottom
  $: pointDist = emptyYears.length > 1 ? (innerW - PADDING.left - PADDING.right) / (emptyYears.length - 1) : 0

  function pointY(v) {
    return PADDING.top + innerH - (v / maxVal) * innerH
  }

  function pointX(i) {
    return PADDING.left + i * pointDist
  }

  function yTick(ratio) {
    return PADDING.top + innerH - ratio * innerH
  }

  $: yTicks = [0, 0.25, 0.5, 0.75, 1].map(r => ({
    y: yTick(r),
    label: Math.round(maxVal * r),
  }))

  let hoveredPoint = null // { x, y, label, value, color, name }
</script>

<div class="glass-card p-6 animate-slide-up h-full flex flex-col">
  {#if title}
    <h3 class="font-bold text-slate-800 dark:text-white mb-4 flex flex-wrap items-center justify-between gap-2">
      <span class="flex items-center gap-2">📈 {title}</span>
      <div class="flex flex-wrap gap-3">
        {#each series as s}
          <div class="flex items-center gap-1.5 text-[10px] font-bold tracking-wider">
            <span class="w-2.5 h-2.5 rounded-full" style="background:{s.color}"></span>
            <span class="text-slate-600 dark:text-slate-300">{s.name}</span>
          </div>
        {/each}
      </div>
    </h3>
  {/if}

  <div class="w-full overflow-x-auto flex-1 flex items-end">
    <svg
      viewBox="0 0 {innerW} {height}"
      class="w-full"
      style="min-width: 320px; height: {height}px;"
      role="img"
      aria-label={title}
    >
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

      <!-- Draw lines -->
      {#each series as s}
        {@const pathData = emptyYears.map((y, i) => {
           const found = s.data.find(d => d[labelKey] === y);
           const val = found ? found[valueKey] : 0;
           return `${i === 0 ? 'M' : 'L'} ${pointX(i)} ${pointY(val)}`;
        }).join(' ')}
        <path
          d={pathData}
          fill="none"
          stroke={s.color}
          stroke-width="3"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      {/each}

      <!-- Draw hover areas and points -->
      {#each series as s}
        {#each emptyYears as y, i}
          {@const found = s.data.find(d => d[labelKey] === y)}
          {@const val = found ? found[valueKey] : 0}
          {@const px = pointX(i)}
          {@const py = pointY(val)}

          <!-- Interactive hit area -->
          <circle
            cx={px}
            cy={py}
            r="16"
            fill="transparent"
            class="cursor-pointer"
            on:mouseenter={() => hoveredPoint = { x: px, y: py, label: y, value: val, color: s.color, name: s.name }}
            on:mouseleave={() => hoveredPoint = null}
          />
          <circle
            cx={px}
            cy={py}
            r="4"
            fill={s.color}
            stroke="currentColor"
            stroke-width="2"
            class="transition-all duration-150 pointer-events-none text-white dark:text-slate-800"
          />
        {/each}
      {/each}

      <!-- X Axis Labels -->
      {#each emptyYears as y, i}
        <text
          x={pointX(i)}
          y={PADDING.top + innerH + 20}
          text-anchor="middle"
          class="fill-slate-500 dark:fill-slate-400 pointer-events-none"
          font-size="10"
        >{y}</text>
      {/each}

      <!-- Tooltip Overlays -->
      {#if hoveredPoint}
        <rect
          x={hoveredPoint.x - 30}
          y={hoveredPoint.y - 36}
          width={60}
          height={24}
          rx="4"
          fill={hoveredPoint.color}
          opacity="0.95"
          class="pointer-events-none shadow-lg"
        />
        <text
          x={hoveredPoint.x}
          y={hoveredPoint.y - 20}
          text-anchor="middle"
          fill="white"
          font-size="10"
          font-weight="700"
          class="pointer-events-none"
        >{hoveredPoint.name}: {hoveredPoint.value}</text>
      {/if}
    </svg>
  </div>
</div>
