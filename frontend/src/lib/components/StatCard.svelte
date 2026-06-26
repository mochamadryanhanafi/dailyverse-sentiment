<script>
  export let value = 0
  export let label = ''
  export let sublabel = ''
  export let gradient = 'from-brand-500 to-brand-700'
</script>

<div class="stat-card animate-fade-in group border-slate-200/70 dark:border-slate-800">
  <div class="flex items-start justify-between gap-3">
    <p class="text-xs font-semibold uppercase tracking-widest text-slate-500 dark:text-slate-400">{label}</p>
    <span class="h-2 w-10 rounded-full bg-gradient-to-r {gradient} opacity-80"></span>
  </div>
  <p class="text-3xl font-extrabold text-slate-900 dark:text-white mt-2 tabular-nums">{value.toLocaleString('id-ID')}</p>
  {#if sublabel}
    <p class="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{sublabel}</p>
  {/if}
</div>
