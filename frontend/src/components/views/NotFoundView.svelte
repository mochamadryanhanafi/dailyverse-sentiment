<script>
  export let navigate;
</script>

<div class="space-y-6 animate-fade-in max-w-4xl mx-auto flex flex-col items-center justify-center min-h-[60vh] text-center">
  <div class="glass-card p-12 sm:p-16 flex flex-col items-center gap-6 w-full relative overflow-hidden">
    <!-- Dekorasi Latar Belakang -->
    <div class="absolute -top-24 -right-24 w-64 h-64 bg-brand-500/10 rounded-full blur-3xl"></div>
    <div class="absolute -bottom-24 -left-24 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl"></div>

    <div class="relative">
      <h1 class="text-9xl font-black text-transparent bg-clip-text bg-gradient-to-br from-brand-500 to-indigo-600 drop-shadow-sm">
        404
      </h1>
      <div class="absolute -bottom-2 left-1/2 -translate-x-1/2 w-24 h-2 bg-brand-500/20 rounded-full blur-sm"></div>
    </div>

    <div class="space-y-2 z-10">
      <h2 class="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-white">
        Halaman Tidak Ditemukan
      </h2>
      <p class="text-slate-500 dark:text-slate-400 max-w-md mx-auto">
        Maaf, tautan atau halaman yang Anda cari mungkin telah dipindahkan, dihapus, atau memang tidak pernah ada di DailyVerse.
      </p>
    </div>

    <button
      class="btn-primary mt-4 z-10 px-6 py-3 text-sm font-semibold flex items-center gap-2 shadow-lg shadow-brand-500/25 hover:-translate-y-1 transition-transform"
      on:click={() => navigate('dashboard')}
    >
      <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
        <path fill-rule="evenodd" d="M9.707 14.707a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 1.414L7.414 9H15a1 1 0 110 2H7.414l2.293 2.293a1 1 0 010 1.414z" clip-rule="evenodd" />
      </svg>
      Kembali ke Dashboard
    </button>
  </div>
</div>
