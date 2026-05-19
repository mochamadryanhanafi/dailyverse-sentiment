<script>
  export let value = 0
  export let label = ''
  export let sublabel = ''
  export let icon = ''
  export let gradient = 'from-brand-500 to-brand-700'
</script>

<div class="stat-card animate-fade-in group">
  <div class="flex items-start justify-between">
    <p class="text-xs font-semibold uppercase tracking-widest text-slate-500 dark:text-slate-400">{label}</p>
    {#if icon}
      <div class="w-9 h-9 rounded-xl bg-gradient-to-br {gradient} flex items-center justify-center text-white text-base shadow-md group-hover:scale-110 transition-transform duration-200">
        {icon}
      </div>
    {/if}
  </div>
  <p class="text-3xl font-extrabold text-slate-900 dark:text-white mt-2 tabular-nums">{value.toLocaleString('id-ID')}</p>
  {#if sublabel}
    <p class="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{sublabel}</p>
  {/if}
</div>
