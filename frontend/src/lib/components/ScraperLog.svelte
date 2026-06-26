<script>
  export let logs = []
  export let isRunning = false
  export let scraped = 0
  export let saved = 0
  export let total = 0

  import { createEventDispatcher } from 'svelte'
  const dispatch = createEventDispatcher()
</script>

<div class="glass-card p-6 flex flex-col gap-4 animate-slide-up">
  <div class="flex items-center justify-between">
    <h2 class="text-lg font-bold text-slate-800 dark:text-white flex items-center gap-2">
      Scraper Log
    </h2>
    {#if isRunning}
      <span class="badge-pending">
        <span class="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse"></span>
        Berjalan…
      </span>
    {/if}
  </div>

  {#if isRunning || logs.length > 0}
    <div class="grid grid-cols-3 gap-3">
      <div class="rounded-xl bg-slate-100 dark:bg-slate-700 p-3 text-center">
        <p class="text-2xl font-extrabold text-brand-600 dark:text-brand-400 tabular-nums">{scraped}</p>
        <p class="text-[10px] uppercase tracking-widest text-slate-500 dark:text-slate-400 mt-0.5">Di-scrape</p>
      </div>
      <div class="rounded-xl bg-slate-100 dark:bg-slate-700 p-3 text-center">
        <p class="text-2xl font-extrabold text-emerald-600 dark:text-emerald-400 tabular-nums">{saved}</p>
        <p class="text-[10px] uppercase tracking-widest text-slate-500 dark:text-slate-400 mt-0.5">Disimpan</p>
      </div>
      <div class="rounded-xl bg-slate-100 dark:bg-slate-700 p-3 text-center">
        <p class="text-2xl font-extrabold text-slate-700 dark:text-slate-200 tabular-nums">{total}</p>
        <p class="text-[10px] uppercase tracking-widest text-slate-500 dark:text-slate-400 mt-0.5">Total DB</p>
      </div>
    </div>
  {/if}

  <div class="bg-slate-900 dark:bg-slate-950 rounded-xl p-4 h-64 overflow-y-auto scrollbar-thin font-mono text-xs text-slate-300 flex flex-col gap-1">
    {#if logs.length === 0}
      <span class="text-slate-500 italic">Menunggu scraper dijalankan…</span>
    {:else}
      {#each logs as log}
        <div class="leading-relaxed {log.type === 'error' ? 'text-red-400' : log.type === 'done' ? 'text-emerald-400' : 'text-slate-300'}">
          <span class="text-slate-500 mr-1">[{log.time}]</span>{log.message}
        </div>
      {/each}
    {/if}
  </div>
</div>
