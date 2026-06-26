<script>
  import { theme, themePalettes } from '../stores/theme.js'

  let currentTheme = { isDark: false, palette: 'academic-blue' }
  let open = false
  theme.subscribe(v => currentTheme = v)

  $: isDark = currentTheme.isDark
  $: currentPalette = themePalettes.find(p => p.id === currentTheme.palette) || themePalettes[0]

  function choosePalette(id) {
    theme.setPalette(id)
    open = false
  }
</script>

<div class="theme-picker relative z-50 flex items-center gap-1 rounded-full border border-slate-200/70 dark:border-slate-700 bg-white/55 dark:bg-slate-800/55 p-1 shadow-sm backdrop-blur-md">
  <button
    class="rounded-full w-9 h-9 p-0 flex items-center justify-center text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
    on:click={() => theme.toggle()}
    aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
    title={isDark ? 'Light mode' : 'Dark mode'}
  >
    {#if isDark}
      <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-amber-400" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 2.25a.75.75 0 01.75.75v1.5a.75.75 0 01-1.5 0V3a.75.75 0 01.75-.75zM7.5 12a4.5 4.5 0 119 0 4.5 4.5 0 01-9 0zM18.894 6.166a.75.75 0 00-1.06-1.06l-1.591 1.59a.75.75 0 101.06 1.061l1.591-1.59zM21.75 12a.75.75 0 01-.75.75h-1.5a.75.75 0 010-1.5H21a.75.75 0 01.75.75zM17.834 18.894a.75.75 0 001.06-1.06l-1.59-1.591a.75.75 0 10-1.061 1.06l1.59 1.591zM12 18a.75.75 0 01.75.75V21a.75.75 0 01-1.5 0v-2.25A.75.75 0 0112 18zM7.758 17.303a.75.75 0 00-1.061-1.06l-1.591 1.59a.75.75 0 001.06 1.061l1.591-1.59zM6 12a.75.75 0 01-.75.75H3a.75.75 0 010-1.5h2.25A.75.75 0 016 12zM6.697 7.757a.75.75 0 001.06-1.06l-1.59-1.591a.75.75 0 00-1.061 1.06l1.59 1.591z"/>
      </svg>
    {:else}
      <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-slate-600 dark:text-slate-300" viewBox="0 0 24 24" fill="currentColor">
        <path fill-rule="evenodd" d="M9.528 1.718a.75.75 0 01.162.819A8.97 8.97 0 009 6a9 9 0 009 9 8.97 8.97 0 003.463-.69.75.75 0 01.981.98 10.503 10.503 0 01-9.694 6.46c-5.799 0-10.5-4.701-10.5-10.5 0-4.368 2.667-8.112 6.46-9.694a.75.75 0 01.818.162z" clip-rule="evenodd"/>
      </svg>
    {/if}
  </button>

  <button
    type="button"
    class="flex h-9 items-center gap-2 rounded-full px-2.5 text-xs font-bold text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
    aria-label="Pilih tema warna"
    aria-expanded={open}
    title="Pilih tema warna"
    on:click={() => (open = !open)}
  >
    <span class="h-4 w-4 rounded-full border-2 border-white shadow-sm" style="background: {currentPalette.swatch}"></span>
    <span class="hidden md:inline max-w-[7rem] truncate">{currentPalette.label}</span>
    <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5 text-slate-400 transition-transform {open ? 'rotate-180' : ''}" viewBox="0 0 20 20" fill="currentColor">
      <path fill-rule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clip-rule="evenodd" />
    </svg>
  </button>

  {#if open}
    <button
      type="button"
      class="fixed inset-0 z-40 cursor-default bg-transparent"
      aria-label="Tutup pilihan tema"
      on:click={() => (open = false)}
    ></button>
    <div class="absolute right-0 top-12 z-[70] w-64 rounded-xl border border-slate-200/80 dark:border-slate-700 bg-white/95 dark:bg-slate-900/95 p-2 shadow-xl backdrop-blur-xl">
      <div class="px-2 pb-2 pt-1">
        <p class="text-[10px] font-bold uppercase tracking-widest text-slate-400">Tema Warna</p>
      </div>
      <div class="grid gap-1">
        {#each themePalettes as palette}
          <button
            type="button"
            class="flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left text-sm font-semibold transition-colors {currentTheme.palette === palette.id ? 'bg-slate-100 dark:bg-slate-800 text-slate-950 dark:text-white' : 'text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/70'}"
            on:click={() => choosePalette(palette.id)}
          >
            <span class="h-5 w-5 rounded-full border-2 border-white shadow-sm shrink-0" style="background: {palette.swatch}"></span>
            <span class="min-w-0 flex-1 truncate">{palette.label}</span>
            {#if currentTheme.palette === palette.id}
              <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-brand-600 dark:text-brand-400" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M16.704 5.29a1 1 0 010 1.42l-7.25 7.2a1 1 0 01-1.41 0L3.296 9.19a1 1 0 011.408-1.42l4.045 4.02 6.546-6.5a1 1 0 011.409 0z" clip-rule="evenodd" />
              </svg>
            {/if}
          </button>
        {/each}
      </div>
    </div>
  {/if}
</div>
