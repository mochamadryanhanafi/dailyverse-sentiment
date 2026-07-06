<script>
  import StatCard from '../../lib/components/StatCard.svelte';
  import LineChart from '../../lib/components/LineChart.svelte';
  import BarChart from '../../lib/components/BarChart.svelte';

  export let annotationCoverage;
  export let sentenceValidationRate;
  export let topSource;
  export let dominantSentiment;
  export let totalArticles;
  export let annotatedArticlesCount;
  export let sentenceStats;
  export let sentimentSeries;
  export let sentimentChartYears;
  export let sourceSeries;
  export let sourceChartYears;
  export let sentimentStats;
  export let sourceStats;
  export let evalMetrics;
  export let evalMismatches;
  export let getSourceStyle;
  export let navigate;
</script>

<div class="space-y-6 animate-fade-in max-w-7xl mx-auto">
  <section class="glass-card p-5 sm:p-7">
    <div class="flex flex-col lg:flex-row lg:items-start justify-between gap-6">
      <div class="max-w-3xl">
        <p class="text-xs font-bold uppercase tracking-widest text-brand-600 dark:text-brand-400">
          Economic Sentiment Analytics
        </p>
        <h2 class="mt-2 text-2xl sm:text-3xl font-black text-slate-950 dark:text-white leading-tight">
          Ringkasan Analisis Sentimen Berita Ekonomi
        </h2>
        <p class="mt-3 text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
          Pantau cakupan data artikel, proses anotasi, ekstraksi kalimat, dan performa model dalam satu layar.
        </p>
      </div>

      <div class="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-2 gap-3 min-w-0 lg:min-w-[22rem]">
        <div class="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/80 dark:bg-slate-900/60 p-3">
          <p class="text-[10px] font-bold uppercase tracking-widest text-slate-400">Coverage</p>
          <p class="mt-1 text-2xl font-black text-emerald-600 dark:text-emerald-400">{annotationCoverage}%</p>
          <p class="text-[11px] text-slate-500 dark:text-slate-400">artikel dianotasi</p>
        </div>
        <div class="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/80 dark:bg-slate-900/60 p-3">
          <p class="text-[10px] font-bold uppercase tracking-widest text-slate-400">Validasi</p>
          <p class="mt-1 text-2xl font-black text-blue-600 dark:text-blue-400">{sentenceValidationRate}%</p>
          <p class="text-[11px] text-slate-500 dark:text-slate-400">kalimat ground truth</p>
        </div>
        <div class="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/80 dark:bg-slate-900/60 p-3">
          <p class="text-[10px] font-bold uppercase tracking-widest text-slate-400">Sumber Utama</p>
          <p class="mt-1 text-lg font-black text-slate-900 dark:text-white truncate">{topSource ? getSourceStyle('', topSource.source).name : '-'}</p>
          <p class="text-[11px] text-slate-500 dark:text-slate-400">{topSource ? topSource.count.toLocaleString('id-ID') : 0} artikel</p>
        </div>
        <div class="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/80 dark:bg-slate-900/60 p-3">
          <p class="text-[10px] font-bold uppercase tracking-widest text-slate-400">Sentimen Dominan</p>
          <p class="mt-1 text-lg font-black text-slate-900 dark:text-white truncate">{dominantSentiment ? dominantSentiment.sentiment : '-'}</p>
          <p class="text-[11px] text-slate-500 dark:text-slate-400">{dominantSentiment ? dominantSentiment.count.toLocaleString('id-ID') : 0} artikel</p>
        </div>
      </div>
    </div>
  </section>

  <div class="grid grid-cols-2 xl:grid-cols-4 gap-4">
    <StatCard
      label="Total Artikel"
      value={totalArticles}
      gradient="from-brand-500 to-indigo-600"
      sublabel="tersimpan di database"
    />
    <StatCard
      label="Artikel Dianotasi"
      value={annotatedArticlesCount}
      gradient="from-emerald-500 to-teal-500"
      sublabel="memiliki label sentimen"
    />
    <StatCard
      label="Total Kalimat"
      value={sentenceStats.total}
      gradient="from-blue-500 to-cyan-500"
      sublabel="tersimpan untuk analisis"
    />
    <StatCard
      label="Kalimat Tervalidasi"
      value={sentenceStats.validated}
      gradient="from-violet-500 to-fuchsia-600"
      sublabel="ground truth ahli"
    />
  </div>

  <div class="grid grid-cols-1 gap-5">
    <LineChart
      series={sentimentSeries}
      emptyYears={sentimentChartYears}
      title="Tren Artikel Berdasarkan Sentimen"
      height={320}
      labelKey="year"
      valueKey="count"
    />
    <LineChart
      series={sourceSeries}
      emptyYears={sourceChartYears}
      title="Tren Artikel Berdasarkan Portal"
      height={320}
      labelKey="year"
      valueKey="count"
    />
    <BarChart
      data={sourceStats}
      title="Total Artikel Berdasarkan Portal"
      height={320}
      labelKey="source"
      valueKey="count"
    />
  </div>

  <div class="grid grid-cols-1 lg:grid-cols-3 gap-5">
    <section class="glass-card p-5 sm:p-6 flex flex-col gap-4">
      <div>
        <h3 class="font-bold text-slate-900 dark:text-white">Distribusi Sentimen</h3>
        <p class="text-xs text-slate-500 dark:text-slate-400 mt-1">Proporsi label artikel dalam dataset.</p>
      </div>
      {#if sentimentStats && sentimentStats.length > 0}
        <div class="space-y-4">
          {#each sentimentStats as stat}
            {@const sentimentName = stat.sentiment === "None" || !stat.sentiment ? "Belum Dianotasi" : stat.sentiment}
            {@const sentimentPct = totalArticles > 0 ? Math.max((stat.count / totalArticles) * 100, 1) : 0}
            <div>
              <div class="flex justify-between items-end mb-1">
                <span class="text-sm font-semibold capitalize text-slate-700 dark:text-slate-300">{sentimentName}</span>
                <span class="text-xs font-bold text-slate-500">{stat.count.toLocaleString("id-ID")}</span>
              </div>
              <div class="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-2.5 shadow-inner overflow-hidden">
                <div
                  class="h-2.5 rounded-full {stat.sentiment?.toLowerCase() === 'positif'
                    ? 'bg-emerald-500'
                    : stat.sentiment?.toLowerCase() === 'negatif'
                      ? 'bg-red-500'
                      : stat.sentiment?.toLowerCase() === 'netral'
                        ? 'bg-blue-500'
                        : 'bg-slate-400'}"
                  style="width: {sentimentPct}%"
                ></div>
              </div>
            </div>
          {/each}
        </div>
      {:else}
        <p class="text-sm text-slate-500 dark:text-slate-400 italic">Belum ada data sentimen.</p>
      {/if}
    </section>

    <section class="glass-card p-5 sm:p-6 flex flex-col gap-4">
      <div>
        <h3 class="font-bold text-slate-900 dark:text-white">Portal Berita</h3>
        <p class="text-xs text-slate-500 dark:text-slate-400 mt-1">Sumber artikel yang masuk database.</p>
      </div>
      {#if sourceStats && sourceStats.length > 0}
        <div class="space-y-4">
          {#each sourceStats as stat}
            {@const sinfo = getSourceStyle('', stat.source)}
            {@const sourcePct = totalArticles > 0 ? Math.max((stat.count / totalArticles) * 100, 1) : 0}
            <div>
              <div class="flex justify-between items-center mb-2">
                <span class="text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded-md border shadow-sm {sinfo.colors}">
                  {sinfo.name}
                </span>
                <span class="text-xs font-bold text-slate-500">{stat.count.toLocaleString("id-ID")}</span>
              </div>
              <div class="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-2.5 shadow-inner overflow-hidden">
                <div class="bg-brand-500 h-2.5 rounded-full" style="width: {sourcePct}%"></div>
              </div>
            </div>
          {/each}
        </div>
      {:else}
        <p class="text-sm text-slate-500 dark:text-slate-400 italic">Belum ada data sumber berita.</p>
      {/if}
    </section>

    <section class="glass-card p-5 sm:p-6 flex flex-col gap-4">
      {#if evalMetrics}
        {@const dashboardWrongSentences = evalMismatches.slice(0, 3)}
        <div class="flex items-start justify-between gap-3">
          <div>
            <h3 class="font-bold text-slate-900 dark:text-white">Evaluasi Model</h3>
            <p class="text-xs text-slate-500 dark:text-slate-400 mt-1">Hasil terhadap data validasi ahli.</p>
          </div>
          <button class="btn-ghost border border-slate-200 dark:border-slate-800 px-3 py-1.5" on:click={() => navigate('evaluasi')}>
            Detail
          </button>
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div class="rounded-lg border border-slate-200 dark:border-slate-800 p-3">
            <p class="text-[10px] font-bold uppercase tracking-widest text-slate-400">Accuracy</p>
            <p class="mt-1 text-2xl font-black text-brand-600 dark:text-brand-400">{(evalMetrics.accuracy * 100).toFixed(2)}%</p>
          </div>
          <div class="rounded-lg border border-slate-200 dark:border-slate-800 p-3">
            <p class="text-[10px] font-bold uppercase tracking-widest text-slate-400">F1-Score</p>
            <p class="mt-1 text-2xl font-black text-indigo-600 dark:text-indigo-400">{(evalMetrics.macro_avg.f1 * 100).toFixed(2)}%</p>
          </div>
          <div class="rounded-lg border border-slate-200 dark:border-slate-800 p-3">
            <p class="text-[10px] font-bold uppercase tracking-widest text-slate-400">Benar</p>
            <p class="mt-1 text-2xl font-black text-emerald-600 dark:text-emerald-400">{evalMetrics.correct.toLocaleString('id-ID')}</p>
          </div>
          <div class="rounded-lg border border-slate-200 dark:border-slate-800 p-3">
            <p class="text-[10px] font-bold uppercase tracking-widest text-slate-400">Salah</p>
            <p class="mt-1 text-2xl font-black text-red-600 dark:text-red-400">{evalMetrics.incorrect.toLocaleString('id-ID')}</p>
          </div>
        </div>
        {#if dashboardWrongSentences.length > 0}
          <div class="space-y-2">
            <p class="text-xs font-bold uppercase tracking-widest text-slate-400">Contoh Salah Prediksi</p>
            {#each dashboardWrongSentences as item}
              <div class="rounded-lg border border-slate-200 dark:border-slate-800 px-3 py-2">
                <p class="text-xs text-slate-600 dark:text-slate-300 line-clamp-2">{item.text}</p>
                <p class="mt-1 text-[11px] text-slate-400">
                  Ahli: <span class="font-semibold">{item.true}</span> · Model: <span class="font-semibold">{item.pred}</span>
                </p>
              </div>
            {/each}
          </div>
        {/if}
      {:else}
        <div>
          <h3 class="font-bold text-slate-900 dark:text-white">Evaluasi Model</h3>
          <p class="text-sm text-slate-500 dark:text-slate-400 mt-2">
            Belum ada hasil evaluasi yang ditampilkan. Jalankan evaluasi untuk melihat accuracy, precision, recall, dan F1-score.
          </p>
        </div>
        <button class="btn-primary justify-center" on:click={() => navigate('evaluasi')}>
          Jalankan Evaluasi
        </button>
      {/if}
    </section>
  </div>
</div>
