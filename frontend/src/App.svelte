<script>
  import { onMount } from "svelte";
  import { theme } from "./lib/stores/theme.js";
  import { api } from "./lib/api/client.js";
  import ThemeToggle from "./lib/components/ThemeToggle.svelte";
  import StatusBadge from "./lib/components/StatusBadge.svelte";
  import StatCard from "./lib/components/StatCard.svelte";
  import BarChart from "./lib/components/BarChart.svelte";
  import LineChart from "./lib/components/LineChart.svelte";

  // Auth State
  let isLoggedIn = false;
  let loginError = "";
  let isLoggingIn = false;
  let userProfile = null;

  // Set Google Client ID
  const GOOGLE_CLIENT_ID =
    "228773643545-ojdnob5n8i76kvihghm60eh261ahhf9l.apps.googleusercontent.com";

  // App State
  let serverStatus = "loading";
  let dbStatus = "loading";
  let articles = [];
  let totalArticles = 0;
  let articlesLimit = 20;
  let articlesOffset = 0;
  let articlesLoading = false;
  let articlesError = "";
  let activeTab = "dashboard";
  let sidebarOpen = false;
  let yearSourceStats = [];
  let yearSentimentStats = [];
  let sourceStats = [];
  let sentimentStats = [];

  $: sourceSeries = Array.from(new Set(yearSourceStats.map(s => s.source))).map((source, i) => {
     const colors = ['#3b82f6', '#f97316', '#eab308', '#10b981', '#ef4444', '#8b5cf6', '#ec4899'];
     return {
       name: source,
       color: colors[i % colors.length],
       data: yearSourceStats.filter(s => s.source === source)
     };
  });

  $: sentimentSeries = ['Positif', 'Negatif', 'Netral', 'Belum Dianotasi'].map((sentiment) => {
     const colors = { 'Positif': '#10b981', 'Negatif': '#ef4444', 'Netral': '#3b82f6', 'Belum Dianotasi': '#94a3b8' };
     return {
       name: sentiment,
       color: colors[sentiment] || '#94a3b8',
       data: yearSentimentStats.filter(s => s.sentiment === sentiment)
     };
  }).filter(s => s.data.length > 0);

  let filterSource = "";
  let filterSentiment = "";
  let filterStartDate = "";
  let filterEndDate = "";
  let sortOrder = "asc";

  // NLP Export State
  let nlpThreshold = 0.8;

  let analyzeText = "";
  let analyzeResult = null;
  let analyzeLoading = false;

  // Preprocessing State
  let prepStats = null;
  let prepRunning = false;
  let prepForce = false;
  let prepBatchSize = 100;
  let prepLogs = [];
  let prepProgress = 0;
  let prepTotal = 0;
  let prepCurrentTitle = "";
  let prepDone = false;
  let prepPreview = null;
  let prepPreviewOffset = 0;
  let prepPreviewLoading = false;
  let prepPreviewFilter = "done";
  let prepStageFilter = "final";
  let prepResetting = false;

  let extractRunning = false;
  let extractProgress = 0;
  let extractTotal = 0;
  let extractExtracted = 0;
  let extractCurrentTitle = "";
  let extractJaccardThreshold = 0.95;

  // Manual Annotation Table (preview after extraction)
  let extractedSentencesPreview = null;
  let extractedSentencesLoading = false;
  let extractedSentencesOffset = 0;

  // Upload Annotated PDF State
  let annotatedPdfFile = null;
  let annotatedPdfUploading = false;
  let annotatedPdfMessage = "";
  let annotatedPdfResult = null;
  let uploadLogs = [];
  // SSE upload progress
  let uploadAbortController = null;
  let uploadPhase = ''; // 'uploading' | 'parsing' | 'deleting' | 'inserting' | 'done' | 'error'
  let uploadProcessed = 0;
  let uploadTotal = 0;
  let uploadInserted = 0;
  let uploadSkipped = 0;
  let uploadCurrentId = '';

  // TF-IDF State
  let tfidfData = null;
  let tfidfLoading = false;
  let tfidfTopN = 20;
  let tfidfSentimentFilter = "all";
  let tfidfActiveView = "chart";

  // Evaluasi Model State
  let evalRunning = false;
  let evalMetrics = null;
  let evalMismatches = [];
  let evalProgress = 0;
  let evalTotal = 0;
  let evalCurrentText = '';
  let evalEventSource = null;
  let evalLimitAll = true;
  let evalLimit = 500;
  let evalMismatchTab = 'table';
  let evalIncludeMismatches = true;

  const YEARS = [2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024];

  const navItems = [
    { id: "dashboard", icon: "📊", label: "Dashboard" },
    { id: "ingestion", icon: "📥", label: "Ingesti Data" },
    { id: "articles", icon: "📰", label: "Artikel" },
    { id: "preprocessing", icon: "🔬", label: "Preprocessing" },
    { id: "tfidf", icon: "📈", label: "Analisis TF-IDF" },
    { id: "evaluasi", icon: "🎯", label: "Evaluasi Model" },
    { id: "realtime", icon: "⚡", label: "Analisis Realtime" },
  ];

  function getSourceStyle(url, source) {
    let sourceName = (source || "Unknown").toLowerCase();
    
    if (sourceName.includes('detik')) return { name: 'Detik', colors: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300 border-blue-200 dark:border-blue-800' };
    if (sourceName.includes('kompas')) return { name: 'Kompas', colors: 'bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300 border-orange-200 dark:border-orange-800' };
    if (sourceName.includes('liputan6')) return { name: 'Liputan6', colors: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300 border-amber-200 dark:border-amber-800' };
    if (sourceName.includes('republika')) return { name: 'Republika', colors: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800' };
    if (sourceName.includes('tempo')) return { name: 'Tempo', colors: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300 border-red-200 dark:border-red-800' };
    if (sourceName.includes('suara')) return { name: 'Suara', colors: 'bg-teal-100 text-teal-800 dark:bg-teal-900/40 dark:text-teal-300 border-teal-200 dark:border-teal-800' };
    
    // Default
    return { name: source ? source : "Unknown", colors: 'bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300 border-slate-200 dark:border-slate-700' };
  }

  async function handleGoogleCallback(response) {
    isLoggingIn = true;
    loginError = "";
    try {
      const res = await api.auth.google(response.credential);
      if (res.access_token) {
        localStorage.setItem("token", res.access_token);
        userProfile = res.user;
        isLoggedIn = true;
        checkHealth();
        loadArticles();
        loadStats();
      }
    } catch (e) {
      console.error(e);
      loginError = "Autentikasi gagal atau terjadi kesalahan di server!";
    } finally {
      isLoggingIn = false;
    }
  }

  function handleLogout() {
    localStorage.removeItem("token");
    isLoggedIn = false;
    userProfile = null;
    activeTab = "dashboard";
  }

  // --- Ingestion ---
  let csvFile = null;
  let uploadingCsv = false;
  let uploadMessage = "";

  async function handleIngestionCsvUpload() {
    if (!csvFile) return;
    uploadingCsv = true;
    uploadMessage = "Mengunggah dan memvalidasi...";
    try {
      const res = await api.ingestion.uploadCsv(csvFile);
      uploadMessage = `Berhasil! ${res.articles_inserted} artikel masuk database.`;
      csvFile = null;
    } catch (e) {
      uploadMessage = `Gagal: ${e.message}`;
    } finally {
      uploadingCsv = false;
    }
  }


  onMount(async () => {
    // Cek token saat aplikasi dimuat
    const token = localStorage.getItem("token");
    if (token) {
      try {
        const user = await api.auth.me();
        userProfile = user;
        isLoggedIn = true;
        checkHealth();
        loadArticles();
        loadStats();
      } catch (e) {
        localStorage.removeItem("token");
      }
    }

    // Load Google Identity Services script
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.onload = () => {
      if (window.google) {
        window.google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: handleGoogleCallback,
          auto_select: false,
          cancel_on_tap_outside: true,
        });

        window.google.accounts.id.renderButton(
          document.getElementById("google-button-div"),
          { theme: "outline", size: "large", shape: "pill", width: "100%" },
        );
      }
    };
    document.head.appendChild(script);
  });

  async function checkHealth() {
    serverStatus = "loading";
    dbStatus = "loading";
    try {
      await api.health.server();
      serverStatus = "ok";
    } catch {
      serverStatus = "error";
    }
    try {
      const r = await api.health.database();
      dbStatus = r.status === "ok" ? "ok" : "error";
    } catch {
      dbStatus = "error";
    }
  }

  async function loadStats() {
    try { 
      const r = await api.scraper.stats(); 
      sourceStats = r.by_source;
      sentimentStats = r.by_sentiment;
      yearSourceStats = r.by_year_source || [];
      yearSentimentStats = r.by_year_sentiment || [];
    } catch { 
      sourceStats = [];
      sentimentStats = [];
      yearSourceStats = [];
      yearSentimentStats = [];
    }
  }

  async function loadArticles() {
    articlesLoading = true;
    articlesError = "";
    try {
      const r = await api.scraper.articles(articlesLimit, articlesOffset, {
        source: filterSource,
        sentiment: filterSentiment,
        startDate: filterStartDate,
        endDate: filterEndDate,
        sortOrder: sortOrder,
      });
      articles = r.items;
      totalArticles = r.total;
    } catch (e) {
      articlesError = e.message;
    } finally {
      articlesLoading = false;
    }
  }

  function downloadNLP() {
    window.location.href = api.nlp.exportSentences(nlpThreshold);
  }

  async function handleCsvUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    csvUploading = true;
    addLog(`Mengunggah file CSV: ${file.name}...`);
    try {
      const res = await api.scraper.uploadCsv(file);
      addLog(
        `Upload selesai! Diimpor: ${res.imported}, Dilewati (Duplikat): ${res.skipped}, Error: ${res.errors}`,
        "done",
      );
      await loadArticles();
      await loadStats();
    } catch (e) {
      addLog(`Error unggah CSV: ${e.message}`, "error");
    } finally {
      csvUploading = false;
      if (fileInput) fileInput.value = "";
    }
  }

  function navigate(id) {
    activeTab = id;
    sidebarOpen = false;
    if (activeTab === "articles") loadArticles();
    if (activeTab === "preprocessing") {
      loadPrepStats();
      loadPrepPreview();
      loadExtractedSentencesPreview();
    }
    if (activeTab === "tfidf") {
      loadTfidf();
    }
  }

  // --- Preprocessing helpers ---
  async function loadPrepStats() {
    try {
      prepStats = await api.preprocessing.stats();
    } catch {
      prepStats = null;
    }
  }

  function runExtraction() {
    if (extractRunning) return;
    extractRunning = true;
    extractProgress = 0;
    extractExtracted = 0;
    extractTotal = 0;

    const eventSource = api.preprocessing.extractSentencesStream(
      extractJaccardThreshold,
    );

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.event === "progress") {
        extractProgress = data.processed;
        extractTotal = data.total;
        extractExtracted = data.extracted;
        extractCurrentTitle = data.current_title || "";
      } else if (data.event === "done") {
        extractProgress = data.processed;
        extractExtracted = data.extracted;
        eventSource.close();
        extractRunning = false;
        loadPrepStats();
      } else if (data.event === "error") {
        console.error("Extraction error:", data.detail);
        eventSource.close();
        extractRunning = false;
      }
    };

    eventSource.onerror = () => {
      eventSource.close();
      extractRunning = false;
    };
  }

  async function loadPrepPreview() {
    prepPreviewLoading = true;
    try {
      prepPreview = await api.preprocessing.preview(
        20,
        prepPreviewOffset,
        prepPreviewFilter,
      );
    } catch {
      prepPreview = null;
    } finally {
      prepPreviewLoading = false;
    }
  }

  async function loadExtractedSentencesPreview() {
    extractedSentencesLoading = true;
    try {
      extractedSentencesPreview = await api.preprocessing.preview(
        20,
        extractedSentencesOffset,
        'all',
      );
    } catch {
      extractedSentencesPreview = null;
    } finally {
      extractedSentencesLoading = false;
    }
  }

  async function loadTfidf() {
    tfidfLoading = true;
    try {
      const params = new URLSearchParams({ top_n: tfidfTopN, sentiment_filter: tfidfSentimentFilter });
      tfidfData = await api.preprocessing.tfidf(tfidfTopN, tfidfSentimentFilter);
    } catch {
      tfidfData = null;
    } finally {
      tfidfLoading = false;
    }
  }

  function addUploadLog(msg, type = 'info') {
    const ts = new Date().toLocaleTimeString('id-ID', { hour12: false });
    const icon = type === 'error' ? '❌' : type === 'warn' ? '⚠️' : type === 'success' ? '✅' : 'ℹ️';
    uploadLogs = [...uploadLogs, { ts, icon, msg, type }];
  }

  async function handleAnnotatedPdfUpload() {
    if (!annotatedPdfFile) return;
    uploadLogs = [];
    annotatedPdfUploading = true;
    annotatedPdfMessage = '';
    annotatedPdfResult = null;
    uploadPhase = 'uploading';
    uploadProcessed = 0;
    uploadTotal = 0;
    uploadInserted = 0;
    uploadSkipped = 0;
    uploadCurrentId = '';

    addUploadLog(`Mulai upload: ${annotatedPdfFile.name} (${(annotatedPdfFile.size/1024).toFixed(1)} KB)`);
    addUploadLog('Mengirim ke server dan parsing PDF…');

    const fileToUpload = annotatedPdfFile;
    annotatedPdfFile = null;

    uploadAbortController = api.preprocessing.uploadAnnotatedPdf(fileToUpload, (ev) => {
      if (ev.event === 'parsed') {
        uploadPhase = 'deleting';
        uploadTotal = ev.total_parsed;
        addUploadLog(`PDF terparsing: ${ev.total_parsed} baris ditemukan`, 'info');

      } else if (ev.event === 'deleting') {
        uploadPhase = 'deleting';
        addUploadLog('Menghapus data ekstraksi lama…', 'info');

      } else if (ev.event === 'deleted') {
        uploadPhase = 'inserting';
        addUploadLog(`🗑️ Data lama dihapus: ${ev.deleted_count} kalimat`, 'info');

      } else if (ev.event === 'progress') {
        uploadPhase = 'inserting';
        uploadProcessed = ev.processed;
        uploadTotal = ev.total;
        uploadInserted = ev.inserted;
        uploadSkipped = ev.skipped;
        uploadCurrentId = ev.current_id || '';

      } else if (ev.event === 'done') {
        uploadPhase = 'done';
        annotatedPdfResult = ev;
        annotatedPdfMessage = ev.message;
        addUploadLog(`✅ Insert: ${ev.inserted} kalimat`, 'success');
        if (ev.skipped > 0) addUploadLog(`⚠️ Dilewati: ${ev.skipped} (tdk ditemukan: ${ev.not_found ?? 0})`, 'warn');
        addUploadLog(`Selesai! Total baris PDF: ${ev.total_parsed}`, 'success');
        annotatedPdfUploading = false;
        uploadAbortController = null;
        loadPrepStats();
        loadExtractedSentencesPreview();

      } else if (ev.event === 'error') {
        uploadPhase = 'error';
        annotatedPdfMessage = `Gagal: ${ev.detail}`;
        addUploadLog(`GAGAL: ${ev.detail}`, 'error');
        annotatedPdfUploading = false;
        uploadAbortController = null;

      } else if (ev.event === 'cancelled') {
        uploadPhase = 'error';
        annotatedPdfMessage = 'Upload dibatalkan oleh pengguna.';
        addUploadLog('Upload dibatalkan.', 'warn');
        annotatedPdfUploading = false;
        uploadAbortController = null;
      }
    });
  }

  function cancelUpload() {
    if (uploadAbortController) {
      uploadAbortController.abort();
      uploadAbortController = null;
    }
  }

  function runEvaluation() {
    if (evalRunning) return;
    evalRunning = true;
    evalMetrics = null;
    evalMismatches = [];
    evalProgress = 0;
    evalTotal = 0;
    evalCurrentText = '';

    const limit = evalLimitAll ? 0 : evalLimit;
    evalEventSource = api.evaluation.runStream(limit, evalIncludeMismatches);

    evalEventSource.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.event === 'progress') {
        evalProgress = data.processed;
        evalTotal = data.total;
        evalCurrentText = data.current_text || '';
      } else if (data.event === 'done') {
        evalMetrics = data.metrics;
        evalMismatches = data.mismatches || [];
        evalRunning = false;
        evalEventSource.close();
        evalEventSource = null;
      } else if (data.event === 'error') {
        evalMetrics = null;
        evalRunning = false;
        evalCurrentText = `❌ ${data.detail}`;
        evalEventSource.close();
        evalEventSource = null;
      }
    };
    evalEventSource.onerror = () => {
      evalRunning = false;
      evalEventSource?.close();
      evalEventSource = null;
    };
  }

  function stopEvaluation() {
    evalEventSource?.close();
    evalEventSource = null;
    evalRunning = false;
  }

  async function runPreprocessing() {
    if (prepRunning) return;
    prepRunning = true;
    prepLogs = [];
    prepProgress = 0;
    prepTotal = 0;
    prepCurrentTitle = "";
    prepDone = false;

    const es = api.preprocessing.runStream(prepForce, prepBatchSize);

    es.onmessage = async (e) => {
      const data = JSON.parse(e.data);
      if (data.event === "progress") {
        prepProgress = data.processed;
        prepTotal = data.total;
        prepCurrentTitle = data.current_title || "";
      } else if (data.event === "done") {
        prepProgress = data.processed;
        prepTotal = data.grand_total || data.processed;
        prepDone = true;
        prepRunning = false;
        es.close();
        prepLogs = [
          ...prepLogs,
          `✅ Selesai! Diproses: ${data.processed}, Dilewati: ${data.skipped}, Total terproses: ${data.total_preprocessed}`,
        ];
        await loadPrepStats();
        await loadPrepPreview();
      } else if (data.event === "error") {
        prepLogs = [...prepLogs, `❌ Error: ${data.detail}`];
        prepRunning = false;
        es.close();
      }
    };
    es.onerror = () => {
      prepLogs = [...prepLogs, "❌ Koneksi SSE terputus."];
      prepRunning = false;
      es.close();
    };
  }

  async function resetPreprocessing() {
    if (
      !confirm(
        "Yakin ingin mereset semua data preprocessing? Data preprocessed_content akan dihapus.",
      )
    )
      return;
    prepResetting = true;
    try {
      const r = await api.preprocessing.reset();
      prepLogs = [`🔄 Reset ${r.reset} artikel. Siap diproses ulang.`];
      prepProgress = 0;
      prepTotal = 0;
      prepDone = false;
      prepPreview = null;
      await loadPrepStats();
    } catch (e) {
      prepLogs = [`❌ Reset gagal: ${e.message}`];
    } finally {
      prepResetting = false;
    }
  }
</script>

{#if !isLoggedIn}
  <div class="liquid-bg min-h-screen flex items-center justify-center p-4">
    <div
      class="glass-card p-8 w-full max-w-sm text-center relative z-10 shadow-2xl"
    >
      <div
        class="w-14 h-14 mx-auto rounded-2xl bg-gradient-to-br from-brand-500 to-indigo-600 flex items-center justify-center shadow-lg mb-6"
      >
        <span class="text-white font-extrabold text-2xl">D</span>
      </div>
      <h2 class="text-2xl font-bold text-slate-900 dark:text-white mb-2">
        DailyVerse
      </h2>
      <p class="text-sm text-slate-500 dark:text-slate-400 mb-6">
        Login untuk masuk ke dashboard
      </p>

      <div class="space-y-4">
        {#if loginError}
          <p class="text-red-500 text-xs font-semibold">{loginError}</p>
        {/if}

        <div id="google-button-div" class="w-full flex justify-center mt-4">
          <!-- Google button will be rendered here -->
        </div>

        {#if isLoggingIn}
          <div
            class="flex items-center justify-center gap-2 mt-4 text-brand-600 dark:text-brand-400"
          >
            <svg class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none"
              ><circle
                class="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                stroke-width="4"
              /><path
                class="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8v8H4z"
              /></svg
            >
            <span class="text-sm font-semibold">Memverifikasi ke Google...</span
            >
          </div>
        {/if}
      </div>
      <div class="mt-6 flex justify-center"><ThemeToggle /></div>
    </div>
  </div>
{:else}
  <div
    class="liquid-bg flex h-screen overflow-hidden transition-colors duration-300"
  >
    {#if sidebarOpen}
      <div
        class="fixed inset-0 z-20 bg-black/40 lg:hidden backdrop-blur-sm"
        on:click={() => (sidebarOpen = false)}
      ></div>
    {/if}

    <aside
      class="
    fixed inset-y-0 left-0 z-30 w-64 flex flex-col
    bg-white/40 dark:bg-slate-900/40 backdrop-blur-3xl border-r border-white/50 dark:border-slate-700/50
    shadow-[4px_0_24px_rgba(0,0,0,0.02)] dark:shadow-[4px_0_24px_rgba(0,0,0,0.2)]
    transition-transform duration-300
    {sidebarOpen
        ? 'translate-x-0'
        : '-translate-x-full'} lg:translate-x-0 lg:static lg:bg-transparent lg:border-r lg:border-slate-200/50 lg:dark:border-slate-700/30
  "
    >
      <div
        class="flex items-center gap-3 px-6 h-20 border-b border-slate-200/50 dark:border-slate-700/50 shrink-0"
      >
        <div
          class="w-10 h-10 rounded-2xl bg-gradient-to-br from-brand-500 to-indigo-600 flex items-center justify-center shadow-lg shrink-0"
        >
          <span class="text-white font-extrabold text-lg">D</span>
        </div>
        <div class="min-w-0">
          <p
            class="font-bold text-slate-900 dark:text-white text-sm leading-tight"
          >
            DailyVerse
          </p>
          <p
            class="text-[10px] text-brand-600 dark:text-brand-400 font-semibold leading-tight mt-0.5"
          >
            Sentiment Analysis
          </p>
        </div>
      </div>

      <nav class="flex-1 overflow-y-auto px-4 py-6 space-y-1.5">
        <p
          class="px-2 pb-2 text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500"
        >
          Menu Utama
        </p>
        {#each navItems as item}
          <button
            class="w-full flex items-center gap-3 px-3 py-3 rounded-2xl text-sm font-semibold transition-all duration-300 relative overflow-hidden group
            {activeTab === item.id
              ? 'bg-white/60 dark:bg-slate-800/60 shadow-[0_4px_12px_rgba(0,0,0,0.05)] text-brand-700 dark:text-brand-300 border border-white/80 dark:border-white/10'
              : 'text-slate-600 dark:text-slate-300 hover:bg-white/30 dark:hover:bg-slate-800/30 border border-transparent'}"
            on:click={() => navigate(item.id)}
          >
            {#if activeTab === item.id}
              <div
                class="absolute inset-0 bg-gradient-to-r from-brand-500/10 to-transparent"
              ></div>
            {/if}
            <span class="text-lg w-6 text-center drop-shadow-sm"
              >{item.icon}</span
            >
            <span class="relative z-10">{item.label}</span>
            {#if item.id === "articles" && totalArticles > 0}
              <span
                class="ml-auto relative z-10 text-[10px] font-bold bg-brand-100 dark:bg-brand-900/50 text-brand-700 dark:text-brand-300 px-2.5 py-0.5 rounded-full shadow-inner"
              >
                {totalArticles}
              </span>
            {/if}
          </button>
        {/each}
      </nav>

      <div
        class="px-5 py-5 border-t border-slate-200/50 dark:border-slate-700/50 space-y-3 shrink-0 bg-white/20 dark:bg-slate-900/20 backdrop-blur-md"
      >
        <div class="flex items-center justify-between">
          <span class="text-xs font-semibold text-slate-500 dark:text-slate-400"
            >API Server</span
          >
          <StatusBadge status={serverStatus} />
        </div>
        <div class="flex items-center justify-between">
          <span class="text-xs font-semibold text-slate-500 dark:text-slate-400"
            >Database</span
          >
          <StatusBadge status={dbStatus} />
        </div>
        <div class="flex items-center justify-between pt-3">
          <button
            class="btn-ghost text-xs px-3 py-1.5 rounded-xl gap-1.5 shadow-sm bg-white/50 dark:bg-slate-800/50 border border-white/60 dark:border-white/5"
            on:click={checkHealth}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              class="w-3.5 h-3.5"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fill-rule="evenodd"
                d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z"
                clip-rule="evenodd"
              />
            </svg>
            Refresh
          </button>
          <ThemeToggle />
        </div>
      </div>
    </aside>

    <div class="flex-1 flex flex-col min-w-0 relative z-10">
      <header
        class="h-20 shrink-0 flex items-center gap-4 px-6 sm:px-8 border-b border-white/20 dark:border-slate-700/30"
      >
        <button
          class="lg:hidden btn-ghost rounded-xl w-10 h-10 p-0 flex items-center justify-center bg-white/50 dark:bg-slate-800/50 backdrop-blur-md"
          on:click={() => (sidebarOpen = !sidebarOpen)}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="w-5 h-5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M4 6h16M4 12h16M4 18h16"
            />
          </svg>
        </button>
        <h1
          class="font-extrabold text-slate-900 dark:text-white text-xl capitalize drop-shadow-sm flex items-center gap-2"
        >
          {navItems.find((n) => n.id === activeTab)?.label}
        </h1>
        <div class="ml-auto flex items-center gap-3">
          {#if userProfile}
            <div
              class="hidden sm:flex items-center gap-3 bg-white/30 dark:bg-slate-800/50 px-3 py-1.5 rounded-full border border-white/40 dark:border-slate-700/50 shadow-sm"
            >
              {#if userProfile.picture}
                <img
                  src={userProfile.picture}
                  alt="Profile"
                  class="w-8 h-8 rounded-full shadow-sm"
                  referrerpolicy="no-referrer"
                />
              {:else}
                <div
                  class="w-8 h-8 rounded-full bg-brand-500 text-white flex items-center justify-center font-bold text-sm"
                >
                  {userProfile.username.charAt(0)}
                </div>
              {/if}
              <div class="flex flex-col">
                <span
                  class="text-xs font-bold text-slate-800 dark:text-slate-100 leading-none"
                  >{userProfile.username}</span
                >
                <span
                  class="text-[10px] font-semibold text-brand-600 dark:text-brand-400 capitalize"
                  >{userProfile.role}</span
                >
              </div>
              <div class="w-px h-6 bg-slate-300 dark:bg-slate-600 mx-1"></div>
              <button
                class="text-slate-500 hover:text-red-500 transition-colors p-1"
                on:click={handleLogout}
                title="Logout"
              >
                <svg
                  class="w-4 h-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  ><path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                  /></svg
                >
              </button>
            </div>
          {/if}
        </div>
      </header>

      <main class="flex-1 overflow-y-auto p-4 sm:p-8 scrollbar-thin">
        {#if activeTab === "dashboard"}
          <div class="space-y-8 animate-fade-in max-w-6xl mx-auto">
            <div class="grid grid-cols-2 lg:grid-cols-4 gap-5">
              <StatCard
                label="Total Artikel"
                value={totalArticles}
                icon="📰"
                gradient="from-brand-500 to-indigo-600"
                sublabel="tersimpan di database"
              />
              <StatCard
                label="Server API"
                value={serverStatus === "ok" ? 1 : 0}
                icon="⚡"
                gradient="from-emerald-500 to-teal-500"
                sublabel={serverStatus === "ok" ? "Online" : "Offline"}
              />
              <StatCard
                label="Database"
                value={dbStatus === "ok" ? 1 : 0}
                icon="🗄️"
                gradient="from-violet-500 to-fuchsia-600"
                sublabel={dbStatus === "ok" ? "Terhubung" : "Terputus"}
              />
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-2 gap-5">
              <div class="flex flex-col gap-3">
                <LineChart
                  series={sourceSeries}
                  emptyYears={YEARS}
                  title="Trend Artikel (Sumber)"
                  height={280}
                  labelKey="year"
                  valueKey="count"
                />
              </div>

              <div class="flex flex-col gap-3">
                <LineChart
                  series={sentimentSeries}
                  emptyYears={YEARS}
                  title="Trend Artikel (Sentimen)"
                  height={280}
                  labelKey="year"
                  valueKey="count"
                />
              </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
              <!-- Sentiment Distribution -->
              <div class="glass-card p-6 flex flex-col gap-4">
                <h3
                  class="font-bold text-slate-800 dark:text-white flex items-center gap-2"
                >
                  <span>🎭</span> Distribusi Sentimen
                </h3>
                {#if sentimentStats && sentimentStats.length > 0}
                  <div class="space-y-4 mt-2">
                    {#each sentimentStats as stat}
                      <div>
                        <div class="flex justify-between items-end mb-1">
                          <span
                            class="text-sm font-semibold capitalize text-slate-700 dark:text-slate-300"
                          >
                            {stat.sentiment === "None" || !stat.sentiment
                              ? "Belum Dianotasi"
                              : stat.sentiment}
                          </span>
                          <span class="text-xs font-bold text-slate-500"
                            >{stat.count.toLocaleString("id-ID")}</span
                          >
                        </div>
                        <div
                          class="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-2.5 shadow-inner overflow-hidden flex"
                        >
                          <div
                            class="h-2.5 rounded-full {stat.sentiment?.toLowerCase() ===
                            'positif'
                              ? 'bg-emerald-500'
                              : stat.sentiment?.toLowerCase() === 'negatif'
                                ? 'bg-red-500'
                                : stat.sentiment?.toLowerCase() === 'netral'
                                  ? 'bg-blue-500'
                                  : 'bg-slate-400'}"
                            style="width: {Math.max(
                              (stat.count / totalArticles) * 100,
                              1,
                            )}%"
                          ></div>
                        </div>
                      </div>
                    {/each}
                  </div>
                {:else}
                  <p class="text-sm text-slate-500 dark:text-slate-400 italic">
                    Belum ada data sentimen.
                  </p>
                {/if}
              </div>

              <!-- Source Distribution -->
              <div class="glass-card p-6 flex flex-col gap-4">
                <h3
                  class="font-bold text-slate-800 dark:text-white flex items-center gap-2"
                >
                  <span>📰</span> Proporsi Portal Berita
                </h3>
                {#if sourceStats && sourceStats.length > 0}
                  <div class="space-y-4 mt-2">
                    {#each sourceStats as stat}
                      {@const sinfo = getSourceStyle('', stat.source)}
                      <div>
                        <div class="flex justify-between items-center mb-2">
                          <span class="text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded-md border shadow-sm {sinfo.colors}">
                            {sinfo.name}
                          </span>
                          <span class="text-xs font-bold text-slate-500">{stat.count.toLocaleString("id-ID")}</span>
                        </div>
                        <div class="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-2.5 shadow-inner overflow-hidden flex">
                          <div class="bg-brand-500 h-2.5 rounded-full" style="width: {Math.max((stat.count / totalArticles) * 100, 1)}%"></div>
                        </div>
                      </div>
                    {/each}
                  </div>
                {:else}
                  <p class="text-sm text-slate-500 dark:text-slate-400 italic">
                    Belum ada data sumber berita.
                  </p>
                {/if}
              </div>
            </div>

            <div class="glass-card p-6 md:p-8">
              <h3
                class="font-bold text-slate-800 dark:text-white mb-3 flex items-center gap-2 text-base"
              >
                <span>ℹ️</span> Tentang Proyek
              </h3>
              <p
                class="text-sm text-slate-600 dark:text-slate-300 leading-relaxed max-w-3xl"
              >
                Dashboard sentimen berita ekonomi Jokowi dari portal <strong
                  >Detik Finance</strong
                >. Menggunakan arsitektur <em>Clean Architecture</em> dengan
                Svelte frontend tema <strong>Liquid Glass</strong>, FastAPI
                backend asinkron, dan PostgreSQL database.
              </p>
            </div>
          </div>
        {:else if activeTab === "articles"}
          <div class="space-y-6 animate-fade-in max-w-5xl mx-auto">
            <div class="glass-card p-4 px-6 flex flex-col gap-4">
              <div class="flex flex-wrap items-center justify-between gap-4">
                <p class="font-bold text-slate-700 dark:text-slate-200">
                  <span class="text-brand-600 dark:text-brand-400 text-lg"
                    >{totalArticles.toLocaleString("id-ID")}</span
                  > artikel tersimpan
                </p>
                <button
                  class="btn-ghost shadow-sm bg-white/50 dark:bg-slate-800/50"
                  on:click={loadArticles}
                  disabled={articlesLoading}
                >
                  {#if articlesLoading}
                    <svg
                      class="w-4 h-4 animate-spin"
                      viewBox="0 0 24 24"
                      fill="none"
                      ><circle
                        class="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        stroke-width="4"
                      /><path
                        class="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8v8H4z"
                      /></svg
                    >
                  {:else}
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      class="w-4 h-4"
                      viewBox="0 0 20 20"
                      fill="currentColor"
                      ><path
                        fill-rule="evenodd"
                        d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z"
                        clip-rule="evenodd"
                      /></svg
                    >
                  {/if}
                  Refresh
                </button>
              </div>

              <div
                class="flex flex-wrap items-center gap-3 pt-4 border-t border-slate-200/50 dark:border-slate-700/50"
              >
                <select
                  bind:value={filterSource}
                  on:change={loadArticles}
                  class="input-field py-1.5 px-3 text-sm shadow-sm bg-white/60 dark:bg-slate-800/60 w-full sm:w-auto"
                >
                  <option value="">Semua Sumber</option>
                  <option value="detik">Detik</option>
                  <option value="kompas">Kompas</option>
                  <option value="liputan6">Liputan6</option>
                  <option value="republika">Republika</option>
                  <option value="suara">Suara</option>
                  <option value="tempo">Tempo</option>
                </select>
                <select
                  bind:value={filterSentiment}
                  on:change={loadArticles}
                  class="input-field py-1.5 px-3 text-sm shadow-sm bg-white/60 dark:bg-slate-800/60 w-full sm:w-auto"
                >
                  <option value="">Semua Sentimen</option>
                  <option value="Positif">Positif</option>
                  <option value="Negatif">Negatif</option>
                  <option value="Netral">Netral</option>
                  <option value="Belum Dianotasi">Belum Dianotasi</option>
                </select>

                <div class="flex items-center gap-2 w-full sm:w-auto">
                  <input
                    type="date"
                    bind:value={filterStartDate}
                    on:change={loadArticles}
                    class="input-field py-1.5 px-3 text-sm shadow-sm bg-white/60 dark:bg-slate-800/60 flex-1"
                    title="Tanggal Mulai"
                  />
                  <span class="text-slate-400 text-sm">-</span>
                  <input
                    type="date"
                    bind:value={filterEndDate}
                    on:change={loadArticles}
                    class="input-field py-1.5 px-3 text-sm shadow-sm bg-white/60 dark:bg-slate-800/60 flex-1"
                    title="Tanggal Akhir"
                  />
                </div>
                <select
                  bind:value={sortOrder}
                  on:change={loadArticles}
                  class="input-field py-1.5 px-3 text-sm shadow-sm bg-white/60 dark:bg-slate-800/60 w-full sm:w-auto"
                >
                  <option value="asc">Terlama Dulu</option>
                  <option value="desc">Terbaru Dulu</option>
                </select>
                <button
                  class="btn-primary py-1.5 px-4 text-sm shadow-sm w-full sm:w-auto"
                  on:click={() => {
                    articlesOffset = 0;
                    loadArticles();
                  }}
                >
                  Filter
                </button>
              </div>
            </div>

            {#if articlesError}
              <div
                class="glass-card p-4 border border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-900/20"
              >
                <p class="text-sm font-semibold text-red-600 dark:text-red-400">
                  ⚠️ {articlesError}
                </p>
              </div>
            {:else if articlesLoading && articles.length === 0}
              <div class="glass-card p-16 flex flex-col items-center gap-4">
                <svg
                  class="w-10 h-10 animate-spin text-brand-500"
                  viewBox="0 0 24 24"
                  fill="none"
                  ><circle
                    class="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    stroke-width="4"
                  /><path
                    class="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8v8H4z"
                  /></svg
                >
                <p class="text-sm font-medium text-slate-500">
                  Memuat artikel dari database…
                </p>
              </div>
            {:else if articles.length === 0}
              <div
                class="glass-card p-16 flex flex-col items-center gap-4 text-center"
              >
                <span class="text-6xl drop-shadow-md">📭</span>
                <p class="text-xl font-bold text-slate-700 dark:text-slate-200">
                  Belum ada artikel
                </p>
                <p class="text-sm text-slate-500 dark:text-slate-400 max-w-md">
                  Database masih kosong. Anda dapat mengunggah dataset melalui menu Ingesti Data.
                </p>
                <button
                  class="btn-primary mt-4 shadow-lg"
                  on:click={() => navigate("ingestion")}>Buka Ingesti Data →</button
                >
              </div>
            {:else}
              <div class="space-y-4">
                {#each articles as article (article.id)}
                  {@const sinfo = getSourceStyle(article.url, article.source)}
                  <div
                    class="glass-card p-5 sm:p-6 hover:-translate-y-1 hover:shadow-2xl transition-all duration-300 group"
                  >
                    <div class="flex flex-col sm:flex-row gap-4">
                      <div class="flex-1 min-w-0">
                        <a
                          href={article.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          class="text-lg font-bold text-slate-900 dark:text-white group-hover:text-brand-600 dark:group-hover:text-brand-400 transition-colors line-clamp-2"
                        >
                          {article.title}
                        </a>
                        <p
                          class="text-sm text-slate-500 dark:text-slate-400 mt-2 line-clamp-3 leading-relaxed"
                        >
                          {article.content}
                        </p>
                      </div>
                      <div
                        class="flex flex-row sm:flex-col items-center sm:items-end justify-between sm:justify-start gap-2 shrink-0 border-t sm:border-t-0 sm:border-l border-slate-200/50 dark:border-slate-700/50 pt-3 sm:pt-0 sm:pl-4 mt-3 sm:mt-0"
                      >
                        <span
                          class="text-xs font-bold tracking-wider bg-brand-100 dark:bg-brand-900/50 text-brand-700 dark:text-brand-300 px-2.5 py-1 rounded-lg"
                        >
                          {new Date(article.date).toLocaleDateString("id-ID", {
                            year: "numeric",
                            month: "short",
                            day: "numeric",
                          })}
                        </span>
                        <a
                          href={article.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          class="text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded-md border shadow-sm transition-all hover:scale-105 flex items-center gap-1 {sinfo.colors}"
                        >
                          Source ↗
                        </a>
                      </div>
                      {#if article.sentiment}
                        <div class="mt-3 sm:mt-0 sm:ml-4 flex items-center">
                          <span
                            class="text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded-full shadow-sm
                          {article.sentiment.toLowerCase() === 'positif'
                              ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300'
                              : article.sentiment.toLowerCase() === 'negatif'
                                ? 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
                                : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'}"
                          >
                            {article.sentiment}
                          </span>
                        </div>
                      {/if}
                    </div>
                  </div>
                {/each}
              </div>

              <div
                class="glass-card p-3 px-5 flex items-center justify-between mt-6"
              >
                <p
                  class="text-sm font-semibold text-slate-500 dark:text-slate-400"
                >
                  Hal. {Math.floor(articlesOffset / articlesLimit) + 1} &mdash;
                  <span class="font-normal"
                    >{articlesOffset + 1}–{Math.min(
                      articlesOffset + articlesLimit,
                      totalArticles,
                    )} dari {totalArticles.toLocaleString("id-ID")}</span
                  >
                </p>
                <div class="flex gap-2">
                  <button
                    class="btn-ghost shadow-sm bg-white/50 dark:bg-slate-800/50"
                    on:click={() => {
                      articlesOffset -= articlesLimit;
                      loadArticles();
                    }}
                    disabled={articlesOffset === 0}>← Prev</button
                  >
                  <button
                    class="btn-ghost shadow-sm bg-white/50 dark:bg-slate-800/50"
                    on:click={() => {
                      articlesOffset += articlesLimit;
                      loadArticles();
                    }}
                    disabled={articlesOffset + articlesLimit >= totalArticles}
                    >Next →</button
                  >
                </div>
              </div>
            {/if}
          </div>

          <!-- SECTION: Ingestion -->
        {:else if activeTab === "ingestion"}
          <div class="p-6 md:p-8 space-y-8 animate-fade-in">
            <div
              class="glass-card p-6 sm:p-8 flex flex-col items-center justify-center text-center space-y-6"
            >
              <div
                class="w-20 h-20 rounded-full bg-brand-100 dark:bg-brand-900/50 flex items-center justify-center text-4xl shadow-inner"
              >
                📥
              </div>
              <div>
                <h2 class="text-2xl font-bold text-slate-800 dark:text-white">
                  Ingesti Data
                </h2>
                <p
                  class="text-slate-500 dark:text-slate-400 mt-2 max-w-lg mx-auto leading-relaxed"
                >
                  Unggah dataset hasil <i>scraping</i> dalam format CSV untuk dimasukkan
                  ke dalam database utama. Kolom yang diwajibkan: Title, Content,
                  URL, Year, Month.
                </p>
              </div>

              <div
                class="w-full max-w-md p-6 bg-slate-50/50 dark:bg-slate-800/30 rounded-2xl border border-dashed border-slate-300 dark:border-slate-600 hover:border-brand-500 transition-colors"
              >
                <input
                  type="file"
                  accept=".csv"
                  class="w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-brand-50 file:text-brand-700 hover:file:bg-brand-100"
                  on:change={(e) => (csvFile = e.target.files[0])}
                  disabled={uploadingCsv}
                />
              </div>

              <button
                class="btn-primary w-full max-w-md shadow-lg shadow-brand-500/30"
                disabled={!csvFile || uploadingCsv}
                on:click={handleIngestionCsvUpload}
              >
                {#if uploadingCsv}Mengunggah...{:else}Unggah ke Database{/if}
              </button>

              {#if uploadMessage}
                <p
                  class="text-sm font-semibold {uploadMessage.startsWith(
                    'Berhasil',
                  )
                    ? 'text-emerald-600'
                    : 'text-red-500'} bg-slate-100 dark:bg-slate-800 px-4 py-2 rounded-lg inline-block"
                >
                  {uploadMessage}
                </p>
              {/if}
            </div>
          </div>
        {:else if activeTab === "preprocessing"}
          <div class="space-y-6 animate-fade-in max-w-5xl mx-auto">
            <!-- Stats Cards -->
            {#if prepStats}
              <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div class="glass-card p-5 flex flex-col gap-1">
                  <p
                    class="text-xs font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500"
                  >
                    Total Artikel
                  </p>
                  <p
                    class="text-3xl font-extrabold text-slate-900 dark:text-white"
                  >
                    {prepStats.total.toLocaleString("id-ID")}
                  </p>
                </div>
                <div class="glass-card p-5 flex flex-col gap-1">
                  <p
                    class="text-xs font-bold uppercase tracking-widest text-emerald-500"
                  >
                    Sudah Diproses
                  </p>
                  <p
                    class="text-3xl font-extrabold text-emerald-600 dark:text-emerald-400"
                  >
                    {prepStats.preprocessed.toLocaleString("id-ID")}
                  </p>
                </div>
                <div class="glass-card p-5 flex flex-col gap-1">
                  <p
                    class="text-xs font-bold uppercase tracking-widest text-amber-500"
                  >
                    Belum Diproses
                  </p>
                  <p
                    class="text-3xl font-extrabold text-amber-600 dark:text-amber-400"
                  >
                    {prepStats.pending.toLocaleString("id-ID")}
                  </p>
                </div>
                <div class="glass-card p-5 flex flex-col gap-1">
                  <p
                    class="text-xs font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500"
                  >
                    Stemmer
                  </p>
                  <p
                    class="text-sm font-bold text-brand-600 dark:text-brand-400 leading-snug"
                  >
                    {prepStats.stemmer}
                  </p>
                </div>
              </div>
            {/if}

            <!-- Tahap 1: Ekstraksi -->
            <div class="glass-card p-6 sm:p-8 space-y-6 mb-8">
              <div
                class="flex flex-col sm:flex-row sm:items-center gap-4 border-b border-slate-200/50 dark:border-slate-700/50 pb-6"
              >
                <div class="flex-1">
                  <h2
                    class="font-bold text-lg text-slate-800 dark:text-white flex items-center gap-2"
                  >
                    Tahap 1: Ekstraksi Kalimat
                  </h2>
                  <p
                    class="text-sm text-slate-500 dark:text-slate-400 mt-1 leading-relaxed"
                  >
                    Memisahkan artikel menjadi kalimat (minimal 70 karakter),
                    membuang kalimat duplikat (kemiripan Jaccard &gt; {Math.round(
                      extractJaccardThreshold * 100,
                    )}%), dan menyiapkan data untuk dianotasi.
                  </p>
                </div>
                <div
                  class="flex flex-col sm:flex-row gap-3 w-full sm:w-auto items-center"
                >
                  <div class="flex flex-col gap-1 w-full sm:w-auto">
                    <label
                      class="text-[10px] uppercase font-bold text-slate-400 tracking-wider"
                      >Batas Jaccard</label
                    >
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      max="1"
                      bind:value={extractJaccardThreshold}
                      disabled={extractRunning}
                      class="input-field py-2 text-sm w-full sm:w-24 text-center"
                    />
                  </div>
                  <button
                    class="btn-primary shadow-xl shadow-brand-500/30 whitespace-nowrap"
                    on:click={runExtraction}
                    disabled={extractRunning || prepRunning || prepResetting}
                  >
                    {#if extractRunning}
                      <svg
                        class="w-4 h-4 animate-spin inline-block mr-2"
                        viewBox="0 0 24 24"
                        fill="none"
                        ><circle
                          class="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          stroke-width="4"
                        /><path
                          class="opacity-75"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8v8H4z"
                        /></svg
                      >
                      Mengekstraksi…
                    {:else}
                      Ekstrak Kalimat
                    {/if}
                  </button>
                  <a
                    href={api.preprocessing.downloadPdfUrl}
                    target="_blank"
                    class="btn-ghost bg-white/50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 shadow-sm flex justify-center items-center whitespace-nowrap px-4 py-2"
                  >
                    Unduh PDF
                  </a>
                </div>
              </div>

              {#if extractRunning || extractProgress > 0}
                <div
                  class="p-4 sm:p-5 bg-slate-50/50 dark:bg-slate-800/30 rounded-2xl border border-slate-100 dark:border-slate-800 space-y-3"
                >
                  <div class="flex items-center justify-between mb-1">
                    <p
                      class="text-sm font-bold text-slate-700 dark:text-slate-200"
                    >
                      {#if extractRunning}Memproses…{:else}Ekstraksi Selesai{/if}
                    </p>
                    <p
                      class="text-sm font-bold text-brand-600 dark:text-brand-400"
                    >
                      {extractProgress.toLocaleString("id-ID")} / {extractTotal.toLocaleString(
                        "id-ID",
                      )} Artikel ({extractExtracted.toLocaleString("id-ID")} Kalimat)
                    </p>
                  </div>
                  <div
                    class="w-full h-3 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden shadow-inner"
                  >
                    <div
                      class="h-full rounded-full transition-all duration-300 ease-out"
                      style="width: {extractTotal > 0
                        ? Math.round((extractProgress / extractTotal) * 100)
                        : 0}%; background: linear-gradient(90deg, #6366f1, #a855f7);"
                    ></div>
                  </div>
                  {#if extractCurrentTitle && extractRunning}
                    <p
                      class="text-xs text-slate-500 dark:text-slate-400 truncate"
                    >
                      <span class="font-semibold">{extractCurrentTitle}</span>
                    </p>
                  {/if}
                </div>
              {/if}
            </div>

            <!-- Tabel Sentimen Manual (setelah ekstraksi) -->
            <div class="glass-card p-6 sm:p-8 space-y-4">
              <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <h3 class="font-bold text-slate-800 dark:text-white flex items-center gap-2">
                    <span>📋</span> Data Kalimat Artikel & Validasi Sentimen Manual
                  </h3>
                  <p class="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Tabel kalimat hasil ekstraksi. Kolom <strong>Sentimen</strong> dan <strong>Validasi</strong> diisi secara manual (unduh PDF → anotasi → unggah kembali).
                  </p>
                </div>
                <button
                  class="btn-ghost text-sm bg-white/50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 whitespace-nowrap"
                  on:click={() => { extractedSentencesOffset = 0; loadExtractedSentencesPreview(); }}
                  disabled={extractedSentencesLoading}
                >
                  {#if extractedSentencesLoading}
                    <svg class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/></svg>
                  {:else}
                    Muat Tabel
                  {/if}
                </button>
              </div>

              {#if extractedSentencesLoading}
                <div class="flex items-center justify-center py-10 gap-3 text-brand-500">
                  <svg class="w-6 h-6 animate-spin" viewBox="0 0 24 24" fill="none"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/></svg>
                  <span class="text-sm font-semibold">Memuat data…</span>
                </div>
              {:else if extractedSentencesPreview && extractedSentencesPreview.items.length > 0}
                <div class="text-xs text-slate-500 dark:text-slate-400 mb-2">
                  Menampilkan {extractedSentencesOffset + 1}–{Math.min(extractedSentencesOffset + 20, extractedSentencesPreview.total)} dari
                  <strong>{extractedSentencesPreview.total.toLocaleString('id-ID')}</strong> kalimat
                </div>
                <div class="overflow-x-auto rounded-2xl border border-slate-200 dark:border-slate-700">
                  <table class="w-full text-xs">
                    <thead>
                      <tr class="bg-slate-100 dark:bg-slate-800">
                        <th class="px-3 py-3 text-left font-bold text-slate-600 dark:text-slate-300 border-b border-slate-200 dark:border-slate-700 whitespace-nowrap">ID Artikel</th>
                        <th class="px-3 py-3 text-left font-bold text-slate-600 dark:text-slate-300 border-b border-slate-200 dark:border-slate-700">Kalimat Asli</th>
                        <th class="px-3 py-3 text-center font-bold text-slate-600 dark:text-slate-300 border-b border-slate-200 dark:border-slate-700 whitespace-nowrap w-24">Sentimen</th>
                        <th class="px-3 py-3 text-center font-bold text-slate-600 dark:text-slate-300 border-b border-slate-200 dark:border-slate-700 whitespace-nowrap w-20">Validasi</th>
                      </tr>
                    </thead>
                    <tbody>
                      {#each extractedSentencesPreview.items as item, idx}
                        {@const src = (item.source || 'UNK').substring(0,3).toUpperCase()}
                        {@const d = item.date ? new Date(item.date) : null}
                        {@const yr = d ? d.getFullYear() : '????'}
                        {@const mo = d ? String(d.getMonth()+1).padStart(2,'0') : '??'}
                        {@const idArt = `${src}-${yr}-${mo}-${String(extractedSentencesOffset + idx + 1).padStart(3,'0')}`}
                        <tr class="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors {idx % 2 === 0 ? '' : 'bg-slate-50/40 dark:bg-slate-800/20'}">
                          <td class="px-3 py-3 font-mono text-brand-700 dark:text-brand-400 font-semibold whitespace-nowrap align-top">{idArt}</td>
                          <td class="px-3 py-3 text-slate-700 dark:text-slate-300 leading-relaxed align-top max-w-lg">{item.original_snippet}</td>
                          <td class="px-3 py-3 text-center align-top">
                            {#if item.sentiment}
                              <span class="inline-block px-2 py-0.5 rounded-full font-bold text-[10px] uppercase tracking-wider
                                {item.sentiment.toLowerCase() === 'positif' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300' :
                                 item.sentiment.toLowerCase() === 'negatif' ? 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300' :
                                 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300'}">
                                {item.sentiment}
                              </span>
                            {:else}
                              <span class="inline-block w-16 h-5 rounded border-2 border-dashed border-slate-300 dark:border-slate-600"></span>
                            {/if}
                          </td>
                          <td class="px-3 py-3 text-center align-top">
                            <span class="inline-block w-12 h-5 rounded border-2 border-dashed border-slate-300 dark:border-slate-600"></span>
                          </td>
                        </tr>
                      {/each}
                    </tbody>
                  </table>
                </div>

                <!-- Pagination -->
                <div class="flex items-center justify-between pt-2">
                  <button
                    class="btn-ghost text-sm bg-white/50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700"
                    on:click={() => { extractedSentencesOffset = Math.max(0, extractedSentencesOffset - 20); loadExtractedSentencesPreview(); }}
                    disabled={extractedSentencesOffset === 0 || extractedSentencesLoading}
                  >← Prev</button>
                  <button
                    class="btn-ghost text-sm bg-white/50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700"
                    on:click={() => { extractedSentencesOffset += 20; loadExtractedSentencesPreview(); }}
                    disabled={extractedSentencesOffset + 20 >= (extractedSentencesPreview?.total ?? 0) || extractedSentencesLoading}
                  >Next →</button>
                </div>
              {:else if extractedSentencesPreview}
                <div class="py-10 text-center">
                  <span class="text-4xl block mb-3">📭</span>
                  <p class="text-sm text-slate-500 dark:text-slate-400">Belum ada kalimat terekstrak. Jalankan Ekstraksi Kalimat terlebih dahulu.</p>
                </div>
              {:else}
                <div class="py-8 text-center">
                  <p class="text-sm text-slate-400 dark:text-slate-500">Klik "Muat Tabel" untuk melihat data kalimat hasil ekstraksi.</p>
                </div>
              {/if}
            </div>

            <!-- Upload PDF Anotasi (sebelum preprocessing) -->
            <div class="glass-card p-6 sm:p-8 space-y-5 border-2 border-dashed border-amber-300 dark:border-amber-700 bg-amber-50/30 dark:bg-amber-900/10">
              <div class="flex items-start gap-4">
                <div class="w-12 h-12 rounded-2xl bg-amber-100 dark:bg-amber-900/50 flex items-center justify-center text-2xl shrink-0">📤</div>
                <div class="flex-1">
                  <h3 class="font-bold text-slate-800 dark:text-white">Unggah PDF Anotasi Manual</h3>
                  <p class="text-sm text-slate-500 dark:text-slate-400 mt-1 leading-relaxed">
                    Setelah mengisi sentimen pada PDF yang diunduh, unggah kembali di sini.
                    <strong class="text-red-600 dark:text-red-400">Seluruh data ekstraksi sebelumnya akan dihapus</strong> dan diganti dengan data dari PDF ini sesuai kode artikelnya.
                  </p>
                  <p class="text-xs text-amber-600 dark:text-amber-400 font-semibold mt-2">
                    Kolom PDF: ID Artikel | Kalimat Asli | Sentimen | Validasi
                  </p>
                </div>
              </div>

              <div class="flex flex-col sm:flex-row items-start sm:items-center gap-4">
                <div class="flex-1 w-full p-4 bg-white/50 dark:bg-slate-800/30 rounded-2xl border border-dashed border-amber-300 dark:border-amber-700 hover:border-amber-500 transition-colors">
                  <input
                    type="file"
                    accept=".pdf"
                    class="w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-amber-50 file:text-amber-700 hover:file:bg-amber-100"
                    on:change={(e) => { annotatedPdfFile = e.target.files[0]; annotatedPdfMessage = ''; annotatedPdfResult = null; uploadLogs = []; }}
                    disabled={annotatedPdfUploading}
                  />
                </div>
                <div class="flex gap-2 shrink-0">
                  <button
                    class="btn-primary bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 shadow-lg shadow-amber-500/30 whitespace-nowrap"
                    disabled={!annotatedPdfFile || annotatedPdfUploading}
                    on:click={handleAnnotatedPdfUpload}
                  >
                    {#if annotatedPdfUploading}
                      <svg class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/></svg>
                      Memproses…
                    {:else}
                      <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM6.293 6.707a1 1 0 010-1.414l3-3a1 1 0 011.414 0l3 3a1 1 0 01-1.414 1.414L11 5.414V13a1 1 0 11-2 0V5.414L7.707 6.707a1 1 0 01-1.414 0z" clip-rule="evenodd"/></svg>
                      Unggah & Ganti Data
                    {/if}
                  </button>
                  {#if annotatedPdfUploading}
                    <button
                      class="px-4 py-2 rounded-2xl bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400 font-semibold text-sm border border-red-200 dark:border-red-800 hover:bg-red-200 dark:hover:bg-red-900/50 transition-colors"
                      on:click={cancelUpload}
                    >✕ Batalkan</button>
                  {/if}
                </div>
              </div>

              <!-- Real-time Upload Progress -->
              {#if annotatedPdfUploading}
                {@const pct = uploadTotal > 0 ? Math.round((uploadProcessed / uploadTotal) * 100) : 0}
                <div class="space-y-3 p-4 bg-amber-50/50 dark:bg-amber-900/10 rounded-2xl border border-amber-200 dark:border-amber-800">
                  <!-- Phase label -->
                  <div class="flex items-center justify-between text-xs font-semibold">
                    <span class="flex items-center gap-2 text-amber-700 dark:text-amber-400">
                      <svg class="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/></svg>
                      {#if uploadPhase === 'uploading'}Mengirim & parsing PDF…
                      {:else if uploadPhase === 'deleting'}Menghapus data lama…
                      {:else if uploadPhase === 'inserting'}Menyimpan kalimat ke database…
                      {:else}Memproses…{/if}
                    </span>
                    <span class="text-slate-500">{pct}%</span>
                  </div>
                  <!-- Progress bar -->
                  <div class="w-full h-2.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden shadow-inner">
                    <div
                      class="h-full rounded-full bg-gradient-to-r from-amber-400 to-orange-500 transition-all duration-300 ease-out"
                      style="width: {uploadPhase === 'uploading' || uploadPhase === 'deleting' ? '0%' : pct + '%'};"
                    ></div>
                  </div>
                  <!-- Counters -->
                  {#if uploadPhase === 'inserting'}
                    <div class="grid grid-cols-4 gap-3 text-center text-xs">
                      <div class="bg-white/60 dark:bg-slate-800/60 rounded-xl p-2.5">
                        <p class="text-slate-400 mb-0.5">Diproses</p>
                        <p class="font-extrabold text-slate-800 dark:text-white text-base">{uploadProcessed}</p>
                        <p class="text-slate-400">/ {uploadTotal}</p>
                      </div>
                      <div class="bg-emerald-50 dark:bg-emerald-900/20 rounded-xl p-2.5">
                        <p class="text-emerald-500 mb-0.5">Tersimpan</p>
                        <p class="font-extrabold text-emerald-600 dark:text-emerald-400 text-base">{uploadInserted}</p>
                      </div>
                      <div class="bg-amber-50 dark:bg-amber-900/20 rounded-xl p-2.5">
                        <p class="text-amber-500 mb-0.5">Dilewati</p>
                        <p class="font-extrabold text-amber-600 dark:text-amber-400 text-base">{uploadSkipped}</p>
                      </div>
                      <div class="bg-white/60 dark:bg-slate-800/60 rounded-xl p-2.5">
                        <p class="text-slate-400 mb-0.5">Sisa</p>
                        <p class="font-extrabold text-slate-600 dark:text-slate-300 text-base">{uploadTotal - uploadProcessed}</p>
                      </div>
                    </div>
                    {#if uploadCurrentId}
                      <p class="text-xs text-slate-400 font-mono truncate">ID saat ini: <span class="text-brand-500">{uploadCurrentId}</span></p>
                    {/if}
                  {/if}
                </div>
              {/if}

              {#if annotatedPdfMessage}
                <div class="flex items-start gap-3 p-4 rounded-2xl {annotatedPdfResult ? 'bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800' : 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800'}">
                  <span class="text-xl shrink-0">{annotatedPdfResult ? '✅' : '❌'}</span>
                  <div>
                    <p class="text-sm font-semibold {annotatedPdfResult ? 'text-emerald-700 dark:text-emerald-300' : 'text-red-600 dark:text-red-400'}">{annotatedPdfMessage}</p>
                    {#if annotatedPdfResult}
                      <div class="flex flex-wrap gap-4 mt-2 text-xs text-slate-500">
                        <span>📥 Diimpor: <strong class="text-emerald-600">{annotatedPdfResult.inserted}</strong></span>
                        <span>⏭️ Dilewati: <strong class="text-amber-600">{annotatedPdfResult.skipped}</strong></span>
                        {#if annotatedPdfResult.not_found > 0}<span>🔍 Tdk Ditemukan: <strong class="text-red-500">{annotatedPdfResult.not_found}</strong></span>{/if}
                        <span>📄 Total Diparsing: <strong>{annotatedPdfResult.total_parsed}</strong></span>
                      </div>
                    {/if}
                  </div>
                </div>
              {/if}

              <!-- Terminal Log Upload -->
              {#if uploadLogs.length > 0}
                <div class="rounded-2xl overflow-hidden border border-slate-800 dark:border-slate-700 bg-[#0d1117] shadow-xl">
                  <div class="flex items-center gap-2 px-4 py-2 bg-slate-800 dark:bg-slate-900 border-b border-slate-700">
                    <div class="flex gap-1.5">
                      <div class="w-3 h-3 rounded-full bg-red-500"></div>
                      <div class="w-3 h-3 rounded-full bg-amber-400"></div>
                      <div class="w-3 h-3 rounded-full bg-emerald-500"></div>
                    </div>
                    <span class="text-xs font-mono text-slate-400 ml-2">upload.log — Terminal</span>
                    <button class="ml-auto text-xs text-slate-500 hover:text-slate-300 transition-colors" on:click={() => (uploadLogs = [])}>Clear</button>
                  </div>
                  <div class="p-4 space-y-1 max-h-48 overflow-y-auto font-mono text-xs leading-relaxed">
                    {#each uploadLogs as entry}
                      <div class="flex items-start gap-2 {entry.type === 'error' ? 'text-red-400' : entry.type === 'warn' ? 'text-amber-400' : entry.type === 'success' ? 'text-emerald-400' : 'text-slate-300'}">
                        <span class="text-slate-500 shrink-0">[{entry.ts}]</span>
                        <span class="shrink-0">{entry.icon}</span>
                        <span class="break-all">{entry.msg}</span>
                      </div>
                    {/each}
                    {#if annotatedPdfUploading}
                      <div class="flex items-center gap-2 text-brand-400">
                        <span class="text-slate-500">[{new Date().toLocaleTimeString('id-ID', {hour12:false})}]</span>
                        <svg class="w-3 h-3 animate-spin shrink-0" viewBox="0 0 24 24" fill="none"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/></svg>
                        <span>Menunggu respons server…</span>
                      </div>
                    {/if}
                  </div>
                </div>
              {/if}
            </div>

            <!-- Pipeline Info + Config + Run -->
            <div class="glass-card p-6 sm:p-8 space-y-6">
              <div
                class="flex flex-col sm:flex-row sm:items-center gap-4 border-b border-slate-200/50 dark:border-slate-700/50 pb-6"
              >
                <div class="flex-1">
                  <h2
                    class="font-bold text-lg text-slate-800 dark:text-white flex items-center gap-2"
                  >
                    Tahap 2: Preprocessing NLP
                  </h2>
                  <p
                    class="text-sm text-slate-500 dark:text-slate-400 mt-1 leading-relaxed"
                  >
                    Memproses kalimat yang telah diekstrak (Tahap 1) dari
                    database melalui tahapan:
                    <span
                      class="font-semibold text-brand-600 dark:text-brand-400"
                      >Cleaning → Case Folding → Tokenisasi → Stopword Removal →
                      Stemming</span
                    >. Hasil disimpan kembali ke kolom
                    <code
                      class="bg-slate-100 dark:bg-slate-800 px-1 py-0.5 rounded text-xs"
                      >preprocessed_content</code
                    >.
                  </p>
                </div>
              </div>

              <!-- Pipeline steps visual -->
              <div
                class="flex flex-wrap items-center gap-2 text-xs font-semibold"
              >
                {#each ["Cleaning", "Case Folding", "Tokenisasi", "Stopword", "Stemming", "Simpan DB"] as step, i}
                  <span
                    class="bg-white/60 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 px-3 py-1.5 rounded-full text-slate-700 dark:text-slate-300 shadow-sm"
                    >{step}</span
                  >
                  {#if i < 5}<span class="text-slate-300 dark:text-slate-600"
                      >→</span
                    >{/if}
                {/each}
              </div>

              <!-- Config -->
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-5">
                <div>
                  <label
                    class="block text-xs font-bold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-2"
                    for="batchSize">Batch Size (artikel per batch)</label
                  >
                  <input
                    id="batchSize"
                    type="number"
                    min="10"
                    max="1000"
                    bind:value={prepBatchSize}
                    class="input-field shadow-inner"
                  />
                </div>
                <div class="flex items-end pb-1">
                  <label
                    class="flex items-center gap-3 cursor-pointer select-none"
                  >
                    <div class="relative">
                      <input
                        type="checkbox"
                        bind:checked={prepForce}
                        class="sr-only peer"
                        id="forceReprocess"
                      />
                      <div
                        class="w-11 h-6 bg-slate-200 dark:bg-slate-700 peer-checked:bg-brand-500 rounded-full transition-colors duration-200"
                      ></div>
                      <div
                        class="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 peer-checked:translate-x-5"
                      ></div>
                    </div>
                    <span
                      class="text-sm font-semibold text-slate-700 dark:text-slate-300"
                      >Paksa Proses Ulang <span
                        class="text-xs font-normal text-slate-400"
                        >(termasuk yg sudah)</span
                      ></span
                    >
                  </label>
                </div>
              </div>

              <!-- Buttons -->
              <div class="flex flex-wrap gap-3">
                <button
                  class="btn-primary shadow-xl shadow-brand-500/30"
                  on:click={runPreprocessing}
                  disabled={prepRunning || prepResetting}
                >
                  {#if prepRunning}
                    <svg
                      class="w-4 h-4 animate-spin"
                      viewBox="0 0 24 24"
                      fill="none"
                      ><circle
                        class="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        stroke-width="4"
                      /><path
                        class="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8v8H4z"
                      /></svg
                    >
                    Sedang Memproses…
                  {:else}
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      class="w-4 h-4"
                      viewBox="0 0 20 20"
                      fill="currentColor"
                      ><path
                        fill-rule="evenodd"
                        d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z"
                        clip-rule="evenodd"
                      /></svg
                    >
                    Jalankan Preprocessing
                  {/if}
                </button>

                <button
                  class="btn-ghost bg-white/50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 shadow-sm"
                  on:click={loadPrepStats}
                  disabled={prepRunning}
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    class="w-4 h-4"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                    ><path
                      fill-rule="evenodd"
                      d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z"
                      clip-rule="evenodd"
                    /></svg
                  >
                  Refresh Stats
                </button>

                <a
                  href={api.preprocessing.downloadCsvUrl}
                  target="_blank"
                  class="btn-ghost bg-white/50 dark:bg-slate-800/50 border border-emerald-200 dark:border-emerald-800 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-900/40 shadow-sm flex justify-center items-center gap-1 {prepRunning ? 'opacity-50 pointer-events-none' : ''}"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clip-rule="evenodd" />
                  </svg>
                  Unduh CSV
                </a>

                <button
                  class="btn-ghost bg-red-50/60 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/40 shadow-sm ml-auto"
                  on:click={resetPreprocessing}
                  disabled={prepRunning || prepResetting}
                >
                  {#if prepResetting}
                    <svg
                      class="w-4 h-4 animate-spin"
                      viewBox="0 0 24 24"
                      fill="none"
                      ><circle
                        class="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        stroke-width="4"
                      /><path
                        class="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8v8H4z"
                      /></svg
                    >
                  {/if}
                  Reset Preprocessing
                </button>
              </div>
            </div>

            <!-- Progress Bar -->
            {#if prepRunning || prepDone || prepProgress > 0}
              <div class="glass-card p-5 sm:p-6 space-y-3">
                <div class="flex items-center justify-between mb-1">
                  <p
                    class="text-sm font-bold text-slate-700 dark:text-slate-200"
                  >
                    {#if prepRunning}⏳ Sedang memproses…{:else if prepDone}✅
                      Selesai{:else}📊 Progress{/if}
                  </p>
                  <p
                    class="text-sm font-bold text-brand-600 dark:text-brand-400"
                  >
                    {prepProgress.toLocaleString("id-ID")} / {prepTotal.toLocaleString(
                      "id-ID",
                    )}
                  </p>
                </div>
                <div
                  class="w-full h-3 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden shadow-inner"
                >
                  <div
                    class="h-full rounded-full transition-all duration-300 ease-out"
                    style="width: {prepTotal > 0
                      ? Math.round((prepProgress / prepTotal) * 100)
                      : 0}%; background: linear-gradient(90deg, #6366f1, #a855f7);"
                  ></div>
                </div>
                {#if prepCurrentTitle && prepRunning}
                  <p
                    class="text-xs text-slate-500 dark:text-slate-400 truncate"
                  >
                    <span class="font-semibold">{prepCurrentTitle}</span>
                  </p>
                {/if}
                {#each prepLogs as log}
                  <p
                    class="text-xs font-mono text-slate-600 dark:text-slate-300 bg-slate-50 dark:bg-slate-900/50 rounded-lg px-3 py-2 border border-slate-100 dark:border-slate-800"
                  >
                    {log}
                  </p>
                {/each}
              </div>
            {/if}

            <!-- Preview hasil preprocessing -->
            <div class="glass-card p-5 sm:p-6 space-y-4">
              <div
                class="flex flex-col sm:flex-row sm:items-center justify-between gap-4"
              >
                <h3
                  class="font-bold text-slate-800 dark:text-white flex items-center gap-2"
                >
                  Preview Hasil Preprocessing
                </h3>
                <div class="flex flex-wrap items-center gap-2">
                  <select
                    bind:value={prepStageFilter}
                    class="input-field py-1.5 px-3 text-sm shadow-sm bg-white/60 dark:bg-slate-800/60 font-semibold text-brand-700 dark:text-brand-300 border-brand-200 dark:border-brand-800"
                  >
                    <option value="final">Hasil Akhir (DB)</option>
                    <option value="cleaned">Tahap 1: Cleaning</option>
                    <option value="tokenized">Tahap 2: Tokenisasi</option>
                    <option value="stopword_removal">Tahap 3: Stopword</option>
                    <option value="stemming">Tahap 4: Stemming</option>
                  </select>

                  <a
                    href={api.preprocessing.downloadStepCsvUrl(prepStageFilter)}
                    target="_blank"
                    class="btn-ghost py-1.5 px-3 text-sm bg-brand-50 dark:bg-brand-900/30 text-brand-600 dark:text-brand-400 border border-brand-200 dark:border-brand-800 shadow-sm flex items-center gap-1 hover:bg-brand-100 dark:hover:bg-brand-900/50"
                    title="Unduh dataset di tahap ini"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
                      <path fill-rule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clip-rule="evenodd" />
                    </svg>
                    Unduh CSV Tahap Ini
                  </a>
                  <select
                    bind:value={prepPreviewFilter}
                    class="input-field py-1.5 px-3 text-sm shadow-sm bg-white/60 dark:bg-slate-800/60"
                    on:change={() => {
                      prepPreviewOffset = 0;
                      loadPrepPreview();
                    }}
                  >
                    <option value="done">Status: Sudah Diproses</option>
                    <option value="pending">Status: Belum Diproses</option>
                    <option value="all">Status: Semua</option>
                  </select>
                  <button
                    class="btn-primary text-sm py-1.5 px-4 shadow-sm"
                    on:click={() => {
                      prepPreviewOffset = 0;
                      loadPrepPreview();
                    }}
                    disabled={prepPreviewLoading}
                  >
                    {#if prepPreviewLoading}
                      <svg
                        class="w-4 h-4 animate-spin"
                        viewBox="0 0 24 24"
                        fill="none"
                        ><circle
                          class="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          stroke-width="4"
                        /><path
                          class="opacity-75"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8v8H4z"
                        /></svg
                      >
                    {:else}
                      Muat Data
                    {/if}
                  </button>
                </div>
              </div>

              {#if prepPreviewLoading}
                <div
                  class="flex items-center justify-center py-10 gap-3 text-brand-500"
                >
                  <svg
                    class="w-6 h-6 animate-spin"
                    viewBox="0 0 24 24"
                    fill="none"
                    ><circle
                      class="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      stroke-width="4"
                    /><path
                      class="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8v8H4z"
                    /></svg
                  >
                  <span class="text-sm font-semibold">Memuat data preview…</span
                  >
                </div>
              {:else if prepPreview && prepPreview.items.length > 0}
                <div
                  class="bg-blue-50/50 dark:bg-blue-900/10 text-blue-800 dark:text-blue-300 p-4 rounded-2xl text-sm leading-relaxed border border-blue-100/50 dark:border-blue-800/30"
                >
                  {#if prepStageFilter === "final"}
                    <strong>Hasil Akhir:</strong> Membandingkan teks asli mentah
                    dengan hasil akhir preprocessing. Kata yang berwarna
                    <span
                      class="text-red-500 bg-red-100 dark:bg-red-900/40 px-1 rounded line-through"
                      >merah dicoret</span
                    >
                    adalah kata/karakter yang dihapus (tanda baca, stopword,
                    imbuhan). Kata yang berwarna
                    <span
                      class="text-emerald-600 font-semibold bg-emerald-100 dark:bg-emerald-900/40 px-1 rounded"
                      >hijau</span
                    > adalah kata hasil akhirnya.
                  {:else if prepStageFilter === "cleaned"}
                    <strong>Tahap 1 Cleaning:</strong> Menghapus elemen pengganggu
                    seperti tag HTML, URL, karakter non-huruf, tanda baca, dan angka
                    dari teks asli. Perhatikan bagian merah yang dibuang.
                  {:else if prepStageFilter === "tokenized"}
                    <strong>Tahap 2 Tokenisasi & Case Folding:</strong> Memecah
                    kalimat menjadi kumpulan kata dan mengubah semuanya menjadi
                    huruf kecil <em>(lowercase)</em>.
                  {:else if prepStageFilter === "stopword_removal"}
                    <strong>Tahap 3 Stopword Removal:</strong> Membuang kata hubung
                    atau kata umum yang tidak memiliki bobot sentimen kuat (contoh:
                    'yang', 'di', 'dan', 'ini'). Kata-kata yang dibuang ditandai
                    merah.
                  {:else if prepStageFilter === "stemming"}
                    <strong>Tahap 4 Stemming:</strong> Mengubah kata berimbuhan menjadi
                    kata dasar (contoh: 'melakukan' → 'laku'). Kata yang berubah
                    ditandai merah (hilang) dan hijau (kata dasar pengganti).
                  {/if}
                </div>
                <div class="text-xs text-slate-500 dark:text-slate-400 mb-2">
                  Menampilkan {prepPreviewOffset + 1}–{Math.min(
                    prepPreviewOffset + 20,
                    prepPreview.total,
                  )} dari
                  <strong>{prepPreview.total.toLocaleString("id-ID")}</strong> kalimat
                  terproses
                </div>
                <div class="space-y-4">
                  {#each prepPreview.items as item}
                    <div
                      class="bg-white/40 dark:bg-slate-900/30 rounded-2xl border border-slate-200/60 dark:border-slate-700/60 overflow-hidden"
                    >
                      <div
                        class="px-4 py-3 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between gap-4"
                      >
                        <p
                          class="text-sm font-bold text-slate-800 dark:text-white line-clamp-1 flex-1"
                        >
                          {item.title}
                        </p>
                        <div class="flex items-center gap-2 shrink-0">
                          {#if item.source}
                            <span
                              class="text-[10px] font-bold uppercase bg-brand-100 dark:bg-brand-900/40 text-brand-700 dark:text-brand-300 px-2 py-0.5 rounded-md"
                              >{item.source}</span
                            >
                          {/if}
                          <span class="text-[10px] text-slate-400"
                            >{item.date}</span
                          >
                        </div>
                      </div>
                      <div
                        class="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-slate-100 dark:divide-slate-800"
                      >
                        <div class="p-4 bg-slate-50/50 dark:bg-slate-800/20">
                          <p
                            class="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2"
                          >
                            Teks Asli
                          </p>
                          <p
                            class="text-xs text-slate-600 dark:text-slate-300 leading-relaxed"
                          >
                            {item.original_snippet}
                          </p>
                        </div>
                        <div class="p-4 bg-brand-50/40 dark:bg-brand-900/10">
                          <p
                            class="text-[10px] font-bold uppercase tracking-widest text-brand-600 dark:text-brand-400 mb-2"
                          >
                            {#if prepStageFilter === "final"}Perbandingan Asli
                              vs Hasil Akhir
                            {:else if prepStageFilter === "cleaned"}Tahap 1:
                              Cleaning
                            {:else if prepStageFilter === "tokenized"}Tahap 2:
                              Tokenisasi
                            {:else if prepStageFilter === "stopword_removal"}Tahap
                              3: Stopword
                            {:else if prepStageFilter === "stemming"}Tahap 4:
                              Stemming
                            {/if}
                          </p>
                          <div
                            class="text-xs text-slate-700 dark:text-slate-200 leading-relaxed font-mono break-words overflow-x-auto"
                          >
                            {#if item.steps && item.steps.diffs}
                              {@html item.steps.diffs[prepStageFilter] || "-"}
                            {:else}
                              -
                            {/if}
                          </div>
                        </div>
                      </div>
                    </div>
                  {/each}
                </div>

                <!-- Pagination -->
                <div class="flex items-center justify-between pt-2">
                  <button
                    class="btn-ghost text-sm bg-white/50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700"
                    on:click={() => {
                      prepPreviewOffset = Math.max(0, prepPreviewOffset - 20);
                      loadPrepPreview();
                    }}
                    disabled={prepPreviewOffset === 0 || prepPreviewLoading}
                    >← Prev</button
                  >
                  <button
                    class="btn-ghost text-sm bg-white/50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700"
                    on:click={() => {
                      prepPreviewOffset += 20;
                      loadPrepPreview();
                    }}
                    disabled={prepPreviewOffset + 20 >=
                      (prepPreview?.total ?? 0) || prepPreviewLoading}
                    >Next →</button
                  >
                </div>
              {:else if prepPreview}
                <div class="py-10 text-center">
                  <span class="text-4xl block mb-3">📭</span>
                  <p class="text-sm text-slate-500 dark:text-slate-400">
                    Belum ada artikel yang diproses. Jalankan pipeline terlebih
                    dahulu.
                  </p>
                </div>
              {:else}
                <div class="py-10 text-center">
                  <p class="text-sm text-slate-400 dark:text-slate-500">
                    Klik "Muat Preview" untuk melihat hasil preprocessing.
                  </p>
                </div>
              {/if}
            </div>
          </div>

          <!-- SECTION: Evaluasi -->
        {:else if activeTab === "evaluasi"}
          <div class="space-y-6 animate-fade-in max-w-5xl mx-auto">
            <!-- Header + Config -->
            <div class="glass-card p-6 sm:p-8">
              <div class="flex flex-col sm:flex-row sm:items-start justify-between gap-6">
                <div>
                  <h2 class="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
                    <span>🎯</span> Evaluasi Model Sentimen
                  </h2>
                  <p class="text-sm text-slate-500 dark:text-slate-400 mt-1 max-w-xl">
                    Bandingkan prediksi model <strong>Logistic Regression + TF-IDF</strong> dengan anotasi manual.
                    Menghasilkan Confusion Matrix, Precision, Recall, F1-Score per kelas dan agregat.
                  </p>
                </div>
                <!-- Config -->
                <div class="flex flex-col gap-3 min-w-[200px]">
                  <label class="flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-300 cursor-pointer">
                    <input type="checkbox" bind:checked={evalLimitAll} class="rounded" />
                    Semua data
                  </label>
                  {#if !evalLimitAll}
                    <div class="flex items-center gap-2">
                      <label class="text-xs font-bold text-slate-500 whitespace-nowrap">Maks:</label>
                      <input type="number" min="10" max="10000" bind:value={evalLimit}
                        class="input-field py-1.5 px-2 text-sm w-24" />
                    </div>
                  {/if}
                  <label class="flex items-center gap-2 text-xs font-semibold text-slate-500 dark:text-slate-400 cursor-pointer">
                    <input type="checkbox" bind:checked={evalIncludeMismatches} class="rounded" />
                    Tampilkan mismatch
                  </label>
                  <div class="flex gap-2 pt-1">
                    {#if !evalRunning}
                      <button class="btn-primary flex items-center gap-2 flex-1 justify-center" on:click={runEvaluation}>
                        <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clip-rule="evenodd"/></svg>
                        Jalankan Evaluasi
                      </button>
                    {:else}
                      <button class="px-4 py-2 rounded-2xl bg-red-100 dark:bg-red-900/30 text-red-600 font-semibold text-sm border border-red-200 flex items-center gap-2 flex-1 justify-center" on:click={stopEvaluation}>
                        <svg class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/></svg>
                        Batalkan
                      </button>
                    {/if}
                  </div>
                </div>
              </div>
            </div>

            <!-- Progress -->
            {#if evalRunning}
              {@const pct = evalTotal > 0 ? Math.round((evalProgress / evalTotal) * 100) : 0}
              <div class="glass-card p-6 space-y-3">
                <div class="flex items-center justify-between text-sm font-semibold">
                  <span class="flex items-center gap-2 text-brand-600 dark:text-brand-400">
                    <svg class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/></svg>
                    Mengevaluasi kalimat…
                  </span>
                  <span class="text-slate-500">{evalProgress} / {evalTotal} ({pct}%)</span>
                </div>
                <div class="w-full h-3 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden shadow-inner">
                  <div class="h-full rounded-full bg-gradient-to-r from-brand-500 to-indigo-500 transition-all duration-500 ease-out" style="width: {pct}%;"></div>
                </div>
                {#if evalCurrentText}
                  <p class="text-xs font-mono text-slate-400 truncate">"{evalCurrentText}"</p>
                {/if}
              </div>
            {/if}

            {#if evalMetrics}
              <!-- Aggregate Metric Cards -->
              <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div class="glass-card p-5 text-center">
                  <p class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">Accuracy</p>
                  <p class="text-4xl font-black text-brand-600 dark:text-brand-400">{(evalMetrics.accuracy * 100).toFixed(1)}<span class="text-xl">%</span></p>
                  <p class="text-xs text-slate-400 mt-1">{evalMetrics.correct}/{evalMetrics.total} benar</p>
                </div>
                <div class="glass-card p-5 text-center">
                  <p class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">Macro F1</p>
                  <p class="text-4xl font-black text-indigo-600 dark:text-indigo-400">{(evalMetrics.macro_avg.f1 * 100).toFixed(1)}<span class="text-xl">%</span></p>
                </div>
                <div class="glass-card p-5 text-center">
                  <p class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">Macro Precision</p>
                  <p class="text-4xl font-black text-emerald-600 dark:text-emerald-400">{(evalMetrics.macro_avg.precision * 100).toFixed(1)}<span class="text-xl">%</span></p>
                </div>
                <div class="glass-card p-5 text-center">
                  <p class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">Macro Recall</p>
                  <p class="text-4xl font-black text-amber-600 dark:text-amber-400">{(evalMetrics.macro_avg.recall * 100).toFixed(1)}<span class="text-xl">%</span></p>
                </div>
              </div>

              <!-- Per-Class + Confusion Matrix row -->
              <div class="grid grid-cols-1 lg:grid-cols-2 gap-5">
                <!-- Per-Class Table -->
                <div class="glass-card p-5 sm:p-6 space-y-4">
                  <h3 class="font-bold text-slate-800 dark:text-white">📋 Metrik Per Kelas</h3>
                  <div class="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700">
                    <table class="w-full text-xs">
                      <thead class="bg-slate-50 dark:bg-slate-800">
                        <tr>
                          <th class="px-4 py-3 text-left font-bold text-slate-600 dark:text-slate-300 border-b border-slate-200 dark:border-slate-700">Kelas</th>
                          <th class="px-4 py-3 text-right font-bold text-slate-600 dark:text-slate-300 border-b">Precision</th>
                          <th class="px-4 py-3 text-right font-bold text-slate-600 dark:text-slate-300 border-b">Recall</th>
                          <th class="px-4 py-3 text-right font-bold text-slate-600 dark:text-slate-300 border-b">F1</th>
                          <th class="px-4 py-3 text-right font-bold text-slate-600 dark:text-slate-300 border-b">Support</th>
                        </tr>
                      </thead>
                      <tbody>
                        {#each evalMetrics.per_class as cls}
                          {@const color = cls.label === 'Positif' ? 'text-emerald-600 dark:text-emerald-400' : cls.label === 'Negatif' ? 'text-red-600 dark:text-red-400' : 'text-blue-600 dark:text-blue-400'}
                          <tr class="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors">
                            <td class="px-4 py-3 font-bold {color}">{cls.label}</td>
                            <td class="px-4 py-3 text-right font-mono text-slate-700 dark:text-slate-300">{(cls.precision*100).toFixed(1)}%</td>
                            <td class="px-4 py-3 text-right font-mono text-slate-700 dark:text-slate-300">{(cls.recall*100).toFixed(1)}%</td>
                            <td class="px-4 py-3 text-right font-bold font-mono {cls.f1 >= 0.8 ? 'text-emerald-600' : cls.f1 >= 0.6 ? 'text-amber-500' : 'text-red-500'}">{(cls.f1*100).toFixed(1)}%</td>
                            <td class="px-4 py-3 text-right text-slate-500">{cls.support}</td>
                          </tr>
                        {/each}
                        <!-- Weighted avg row -->
                        <tr class="bg-slate-50/60 dark:bg-slate-800/40 font-semibold">
                          <td class="px-4 py-3 text-slate-500 text-[11px] uppercase tracking-wide">Weighted Avg</td>
                          <td class="px-4 py-3 text-right font-mono text-slate-600 dark:text-slate-300">{(evalMetrics.weighted_avg.precision*100).toFixed(1)}%</td>
                          <td class="px-4 py-3 text-right font-mono text-slate-600 dark:text-slate-300">{(evalMetrics.weighted_avg.recall*100).toFixed(1)}%</td>
                          <td class="px-4 py-3 text-right font-bold font-mono text-brand-600 dark:text-brand-400">{(evalMetrics.weighted_avg.f1*100).toFixed(1)}%</td>
                          <td class="px-4 py-3 text-right text-slate-500">{evalMetrics.total}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                <!-- Confusion Matrix Heatmap -->
                <div class="glass-card p-5 sm:p-6 space-y-4">
                  <h3 class="font-bold text-slate-800 dark:text-white">🔲 Confusion Matrix</h3>
                  <p class="text-xs text-slate-400">Baris = Label Sebenarnya · Kolom = Prediksi Model</p>
                  {#if evalMetrics.confusion_matrix}
                    {@const cm = evalMetrics.confusion_matrix}
                    {@const labels = evalMetrics.labels}
                    {@const maxVal = Math.max(...cm.flat())}
                    <div class="overflow-x-auto">
                      <table class="w-full text-xs border-collapse">
                        <thead>
                          <tr>
                            <th class="p-2 text-left text-slate-400 text-[10px]">Aktual ↓ / Prediksi →</th>
                            {#each labels as lbl}
                              <th class="p-2 text-center font-bold {lbl === 'Positif' ? 'text-emerald-600' : lbl === 'Negatif' ? 'text-red-600' : 'text-blue-600'}">{lbl}</th>
                            {/each}
                          </tr>
                        </thead>
                        <tbody>
                          {#each cm as row, ri}
                            <tr>
                              <td class="p-2 font-bold text-[11px] {labels[ri] === 'Positif' ? 'text-emerald-600' : labels[ri] === 'Negatif' ? 'text-red-600' : 'text-blue-600'}">{labels[ri]}</td>
                              {#each row as cell, ci}
                                {@const intensity = maxVal > 0 ? cell / maxVal : 0}
                                {@const isDiag = ri === ci}
                                <td class="p-0">
                                  <div
                                    class="m-1 rounded-xl flex flex-col items-center justify-center p-3 transition-all"
                                    style="background: {isDiag ? `rgba(16,185,129,${0.1 + intensity * 0.7})` : `rgba(239,68,68,${intensity * 0.5})`}; min-width: 60px;"
                                  >
                                    <span class="font-black text-xl {isDiag ? 'text-emerald-700 dark:text-emerald-300' : cell > 0 ? 'text-red-600 dark:text-red-400' : 'text-slate-300 dark:text-slate-600'}">{cell}</span>
                                    <span class="text-[9px] {isDiag ? 'text-emerald-500' : 'text-slate-400'}">{maxVal > 0 ? (intensity * 100).toFixed(0) : 0}%</span>
                                  </div>
                                </td>
                              {/each}
                            </tr>
                          {/each}
                        </tbody>
                      </table>
                    </div>
                    <!-- Legend -->
                    <div class="flex gap-4 text-[10px] text-slate-400">
                      <span class="flex items-center gap-1"><span class="w-3 h-3 rounded bg-emerald-300 inline-block"></span> Benar (diagonal)</span>
                      <span class="flex items-center gap-1"><span class="w-3 h-3 rounded bg-red-300 inline-block"></span> Salah prediksi</span>
                    </div>
                  {/if}
                </div>
              </div>

              <!-- Mismatch Table -->
              {#if evalMismatches.length > 0}
                <div class="glass-card p-5 sm:p-6 space-y-4">
                  <div class="flex items-center justify-between">
                    <h3 class="font-bold text-slate-800 dark:text-white flex items-center gap-2">
                      <span>⚠️</span> Prediksi Salah (top {evalMismatches.length})
                    </h3>
                    <span class="text-xs px-2 py-1 bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400 rounded-full font-semibold">{evalMismatches.length} mismatch</span>
                  </div>
                  <div class="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700 max-h-80 overflow-y-auto">
                    <table class="w-full text-xs">
                      <thead class="bg-slate-50 dark:bg-slate-800 sticky top-0">
                        <tr>
                          <th class="px-4 py-3 text-left font-bold text-slate-600 dark:text-slate-300 border-b border-slate-200 dark:border-slate-700">Kalimat (truncated)</th>
                          <th class="px-4 py-3 text-center font-bold text-slate-600 border-b w-28">Label Asli</th>
                          <th class="px-4 py-3 text-center font-bold text-slate-600 border-b w-28">Prediksi</th>
                          <th class="px-4 py-3 text-right font-bold text-slate-600 border-b w-20">Conf.</th>
                        </tr>
                      </thead>
                      <tbody>
                        {#each evalMismatches as mm, i}
                          <tr class="border-b border-slate-100 dark:border-slate-800 hover:bg-red-50/30 dark:hover:bg-red-900/10 transition-colors {i % 2 === 0 ? '' : 'bg-slate-50/40 dark:bg-slate-800/20'}">
                            <td class="px-4 py-2.5 text-slate-600 dark:text-slate-300 font-mono max-w-xs truncate" title={mm.text}>{mm.text}</td>
                            <td class="px-4 py-2.5 text-center">
                              <span class="px-2 py-0.5 rounded-full font-semibold {mm.true === 'Positif' ? 'bg-emerald-100 text-emerald-700' : mm.true === 'Negatif' ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700'}">{mm.true}</span>
                            </td>
                            <td class="px-4 py-2.5 text-center">
                              <span class="px-2 py-0.5 rounded-full font-semibold bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">{mm.pred}</span>
                            </td>
                            <td class="px-4 py-2.5 text-right font-mono text-slate-500">{(mm.confidence * 100).toFixed(0)}%</td>
                          </tr>
                        {/each}
                      </tbody>
                    </table>
                  </div>
                </div>
              {/if}

            {:else if !evalRunning}
              <div class="glass-card p-20 flex flex-col items-center gap-4 text-center">
                <span class="text-7xl drop-shadow-lg">🎯</span>
                <p class="text-xl font-bold text-slate-700 dark:text-slate-200">Siap Mengevaluasi Model</p>
                <p class="text-sm text-slate-500 dark:text-slate-400 max-w-md">
                  Klik <strong>Jalankan Evaluasi</strong> untuk membandingkan prediksi model otomatis
                  dengan anotasi manual yang tersimpan di database.
                </p>
                <p class="text-xs text-slate-400 dark:text-slate-500">
                  Pastikan data telah melalui tahap: Upload PDF → Preprocessing → kemudian evaluasi.
                </p>
              </div>
            {/if}
          </div>

          <!-- SECTION: TF-IDF -->
        {:else if activeTab === "tfidf"}

          <div class="space-y-6 animate-fade-in max-w-6xl mx-auto">
            <!-- Header & Controls -->
            <div class="glass-card p-6 sm:p-8">
              <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <h2 class="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
                    <span>📈</span> Analisis TF-IDF
                  </h2>
                  <p class="text-sm text-slate-500 dark:text-slate-400 mt-1 max-w-xl">
                    Term Frequency–Inverse Document Frequency dari kalimat yang telah dipreprocessing,
                    dikelompokkan per sentimen untuk melihat kata kunci dominan setiap kategori.
                  </p>
                </div>
                <div class="flex flex-wrap gap-3 shrink-0">
                  <select
                    bind:value={tfidfSentimentFilter}
                    class="input-field py-1.5 px-3 text-sm shadow-sm bg-white/60 dark:bg-slate-800/60"
                  >
                    <option value="all">Semua Sentimen</option>
                    <option value="Positif">Positif Saja</option>
                    <option value="Negatif">Negatif Saja</option>
                    <option value="Netral">Netral Saja</option>
                  </select>
                  <div class="flex items-center gap-2">
                    <label class="text-xs font-bold text-slate-500 dark:text-slate-400 whitespace-nowrap">Top-N:</label>
                    <input
                      type="number" min="5" max="1000" bind:value={tfidfTopN}
                      class="input-field py-1.5 px-2 text-sm w-16 text-center shadow-sm"
                    />
                  </div>
                  <button
                    class="btn-primary shadow-xl shadow-brand-500/30 flex items-center gap-2"
                    on:click={loadTfidf}
                    disabled={tfidfLoading}
                  >
                    {#if tfidfLoading}
                      <svg class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/></svg>
                      Menghitung…
                    {:else}
                      <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"/></svg>
                      Hitung TF-IDF
                    {/if}
                  </button>
                  <a
                    href={api.preprocessing.downloadTfidfCsvUrl(tfidfTopN, tfidfSentimentFilter)}
                    target="_blank"
                    class="btn-ghost flex items-center gap-2 border border-slate-200 dark:border-slate-700 bg-white/50 dark:bg-slate-800/50 shadow-sm px-4 py-2"
                    title="Unduh hasil sebagai CSV"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-emerald-600 dark:text-emerald-400" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clip-rule="evenodd"/></svg>
                    CSV
                  </a>
                </div>
              </div>
            </div>

            {#if tfidfLoading}
              <div class="glass-card p-20 flex flex-col items-center gap-4">
                <svg class="w-12 h-12 animate-spin text-brand-500" viewBox="0 0 24 24" fill="none"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/></svg>
                <p class="text-sm font-semibold text-slate-500">Menghitung TF-IDF dari {tfidfTopN} term teratas…</p>
              </div>
            {:else if tfidfData && tfidfData.total_sentences > 0}
              <!-- Summary Stats -->
              <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div class="glass-card p-5 flex flex-col gap-1">
                  <p class="text-xs font-bold uppercase tracking-widest text-slate-400">Total Kalimat</p>
                  <p class="text-3xl font-extrabold text-slate-900 dark:text-white">{tfidfData.total_sentences.toLocaleString('id-ID')}</p>
                </div>
                {#each tfidfData.results as group}
                  <div class="glass-card p-5 flex flex-col gap-1">
                    <p class="text-xs font-bold uppercase tracking-widest {group.sentiment === 'Positif' ? 'text-emerald-500' : group.sentiment === 'Negatif' ? 'text-red-500' : 'text-blue-500'}">{group.sentiment}</p>
                    <p class="text-3xl font-extrabold {group.sentiment === 'Positif' ? 'text-emerald-600 dark:text-emerald-400' : group.sentiment === 'Negatif' ? 'text-red-600 dark:text-red-400' : 'text-blue-600 dark:text-blue-400'}">{group.doc_count.toLocaleString('id-ID')}</p>
                    <p class="text-xs text-slate-400">kalimat</p>
                  </div>
                {/each}
              </div>

              <!-- Per-Sentiment TF-IDF Charts -->
              <div class="grid grid-cols-1 lg:grid-cols-3 gap-5">
                {#each tfidfData.results as group}
                  {@const maxScore = group.terms.length > 0 ? Math.max(...group.terms.map(t => t.score)) : 1}
                  {@const sentColor = group.sentiment === 'Positif' ? {bar: '#10b981', glow: 'shadow-emerald-500/20', badge: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300', border: 'border-emerald-200 dark:border-emerald-800'} : group.sentiment === 'Negatif' ? {bar: '#ef4444', glow: 'shadow-red-500/20', badge: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300', border: 'border-red-200 dark:border-red-800'} : {bar: '#3b82f6', glow: 'shadow-blue-500/20', badge: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300', border: 'border-blue-200 dark:border-blue-800'}}
                  <div class="glass-card p-5 sm:p-6 space-y-4 border {sentColor.border}">
                    <div class="flex items-center justify-between">
                      <h3 class="font-bold text-slate-800 dark:text-white flex items-center gap-2">
                        <span class="inline-block px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wide {sentColor.badge}">{group.sentiment}</span>
                        <span class="text-xs font-normal text-slate-400">({group.doc_count} kalimat)</span>
                      </h3>
                      <span class="text-xs text-slate-400">Top {group.terms.length}</span>
                    </div>
                    <div class="space-y-2">
                      {#each group.terms as term}
                        <div class="flex items-center gap-2 group">
                          <span class="w-20 text-xs font-semibold text-slate-700 dark:text-slate-300 truncate text-right shrink-0 group-hover:text-brand-600 dark:group-hover:text-brand-400 transition-colors" title={term.term}>{term.term}</span>
                          <div class="flex-1 h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden shadow-inner">
                            <div
                              class="h-full rounded-full transition-all duration-700 ease-out"
                              style="width: {(term.score / maxScore) * 100}%; background-color: {sentColor.bar}; opacity: 0.85;"
                            ></div>
                          </div>
                          <span class="w-14 text-[10px] text-slate-400 font-mono shrink-0">{term.score.toFixed(4)}</span>
                        </div>
                      {/each}
                    </div>
                  </div>
                {/each}
              </div>

              <!-- Overall TF-IDF Table -->
              {#if tfidfData.overall && tfidfData.overall.length > 0}
                <div class="glass-card p-5 sm:p-6 space-y-4">
                  <div class="flex items-center justify-between">
                    <h3 class="font-bold text-slate-800 dark:text-white flex items-center gap-2">
                      <span>🌐</span> Top Term Keseluruhan (TF-IDF Global)
                    </h3>
                    <div class="flex gap-2">
                      <button
                        class="text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors {tfidfActiveView === 'chart' ? 'bg-brand-100 text-brand-700 dark:bg-brand-900/40 dark:text-brand-300' : 'bg-slate-100 dark:bg-slate-800 text-slate-500'}"
                        on:click={() => (tfidfActiveView = 'chart')}
                      >Grafik</button>
                      <button
                        class="text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors {tfidfActiveView === 'table' ? 'bg-brand-100 text-brand-700 dark:bg-brand-900/40 dark:text-brand-300' : 'bg-slate-100 dark:bg-slate-800 text-slate-500'}"
                        on:click={() => (tfidfActiveView = 'table')}
                      >Tabel</button>
                    </div>
                  </div>

                  {#if tfidfActiveView === 'chart'}
                    {@const maxOverall = Math.max(...tfidfData.overall.map(t => t.score))}
                    <div class="space-y-2">
                      {#each tfidfData.overall as term, i}
                        <div class="flex items-center gap-3 group">
                          <span class="w-6 text-[10px] font-bold text-slate-400 text-right shrink-0">{i+1}</span>
                          <span class="w-24 text-xs font-semibold text-slate-700 dark:text-slate-300 truncate text-right shrink-0 group-hover:text-brand-600 dark:group-hover:text-brand-400 transition-colors" title={term.term}>{term.term}</span>
                          <div class="flex-1 h-2.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden shadow-inner">
                            <div
                              class="h-full rounded-full bg-gradient-to-r from-brand-500 to-indigo-500 transition-all duration-700 ease-out"
                              style="width: {(term.score / maxOverall) * 100}%;"
                            ></div>
                          </div>
                          <span class="w-16 text-[10px] text-slate-400 font-mono shrink-0">{term.score.toFixed(4)}</span>
                          <span class="w-12 text-[10px] text-slate-400 text-right shrink-0">df: {term.df}</span>
                        </div>
                      {/each}
                    </div>
                  {:else}
                    <div class="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700">
                      <table class="w-full text-xs">
                        <thead class="bg-slate-50 dark:bg-slate-800">
                          <tr>
                            <th class="px-4 py-3 text-left font-bold text-slate-600 dark:text-slate-300 border-b border-slate-200 dark:border-slate-700">#</th>
                            <th class="px-4 py-3 text-left font-bold text-slate-600 dark:text-slate-300 border-b border-slate-200 dark:border-slate-700">Term</th>
                            <th class="px-4 py-3 text-right font-bold text-slate-600 dark:text-slate-300 border-b border-slate-200 dark:border-slate-700">Skor TF-IDF</th>
                            <th class="px-4 py-3 text-right font-bold text-slate-600 dark:text-slate-300 border-b border-slate-200 dark:border-slate-700">Doc Freq</th>
                          </tr>
                        </thead>
                        <tbody>
                          {#each tfidfData.overall as term, i}
                            <tr class="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors {i % 2 === 0 ? '' : 'bg-slate-50/40 dark:bg-slate-800/20'}">
                              <td class="px-4 py-2.5 text-slate-400 font-mono">{i+1}</td>
                              <td class="px-4 py-2.5 font-semibold text-slate-800 dark:text-slate-200 font-mono">{term.term}</td>
                              <td class="px-4 py-2.5 text-right font-mono text-brand-600 dark:text-brand-400 font-bold">{term.score.toFixed(6)}</td>
                              <td class="px-4 py-2.5 text-right text-slate-500">{term.df}</td>
                            </tr>
                          {/each}
                        </tbody>
                      </table>
                    </div>
                  {/if}
                </div>
              {/if}

            {:else if tfidfData}
              <div class="glass-card p-20 flex flex-col items-center gap-4 text-center">
                <span class="text-6xl drop-shadow-md">📊</span>
                <p class="text-xl font-bold text-slate-700 dark:text-slate-200">Belum ada data TF-IDF</p>
                <p class="text-sm text-slate-500 dark:text-slate-400 max-w-md">
                  Pastikan kalimat sudah diekstrak, dianotasi sentimen, dan dipreprocessing terlebih dahulu.
                  Kemudian klik <strong>Hitung TF-IDF</strong>.
                </p>
                <button class="btn-primary mt-2" on:click={() => navigate('preprocessing')}>
                  → Ke Preprocessing
                </button>
              </div>
            {:else}
              <div class="glass-card p-16 text-center">
                <p class="text-slate-400 dark:text-slate-500 text-sm">
                  Klik <strong>Hitung TF-IDF</strong> untuk memulai komputasi.
                </p>
              </div>
            {/if}
          </div>

        {:else if activeTab === "realtime"}
          <div class="space-y-6 animate-fade-in max-w-4xl mx-auto">
            <div class="glass-card p-6 sm:p-10">
              <div class="text-center mb-8">
                <span class="text-6xl drop-shadow-lg block mb-6">⚡</span>
                <h2
                  class="text-2xl font-bold text-slate-900 dark:text-white mb-3"
                >
                  Analisis Sentimen Realtime
                </h2>
                <p
                  class="text-slate-600 dark:text-slate-300 max-w-2xl mx-auto leading-relaxed"
                >
                  Ketik atau salin teks berita di bawah ini untuk melihat
                  prediksi sentimen menggunakan model Logistic Regression yang
                  telah dilatih.
                </p>
              </div>

              <div class="space-y-4">
                <textarea
                  bind:value={analyzeText}
                  class="input-field min-h-[150px] p-4 text-sm resize-y"
                  placeholder="Masukkan teks yang ingin dianalisis di sini..."
                ></textarea>

                <div class="flex justify-end">
                  <button
                    class="btn-primary px-8 py-3 text-base shadow-xl shadow-brand-500/30"
                    on:click={async () => {
                      if (!analyzeText.trim()) return;
                      analyzeLoading = true;
                      try {
                        analyzeResult = await api.nlp.analyze(analyzeText);
                      } catch (e) {
                        analyzeResult = { sentiment: "Error", confidence: 0 };
                      } finally {
                        analyzeLoading = false;
                      }
                    }}
                    disabled={analyzeLoading || !analyzeText.trim()}
                  >
                    {#if analyzeLoading}
                      <svg
                        class="w-5 h-5 animate-spin inline-block mr-2"
                        viewBox="0 0 24 24"
                        fill="none"
                        ><circle
                          class="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          stroke-width="4"
                        /><path
                          class="opacity-75"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8v8H4z"
                        /></svg
                      >
                      Menganalisis...
                    {:else}
                      Mulai Analisis
                    {/if}
                  </button>
                </div>
              </div>

              {#if analyzeResult}
                <div
                  class="mt-8 grid grid-cols-1 {analyzeResult.tfidf_features
                    ?.length > 0
                    ? 'lg:grid-cols-2'
                    : ''} gap-6 animate-fade-in"
                >
                  <!-- Hasil Prediksi -->
                  <div
                    class="p-6 rounded-2xl bg-white/50 dark:bg-slate-900/50 border border-white/40 dark:border-slate-700/50 shadow-inner flex flex-col items-center justify-center text-center"
                  >
                    <p
                      class="text-sm font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-4"
                    >
                      Hasil Prediksi
                    </p>
                    <span
                      class="text-4xl font-extrabold uppercase tracking-widest px-6 py-2 rounded-xl shadow-md mb-3
                    {analyzeResult.sentiment.toLowerCase() === 'positif'
                        ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/60 dark:text-emerald-300'
                        : analyzeResult.sentiment.toLowerCase() === 'negatif'
                          ? 'bg-red-100 text-red-700 dark:bg-red-900/60 dark:text-red-300'
                          : 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300'}"
                    >
                      {analyzeResult.sentiment}
                    </span>
                    <p class="text-slate-600 dark:text-slate-300">
                      Tingkat Keyakinan: <strong
                        >{(analyzeResult.confidence * 100).toFixed(2)}%</strong
                      >
                    </p>
                  </div>

                  <!-- TF-IDF Features -->
                  {#if analyzeResult.tfidf_features && analyzeResult.tfidf_features.length > 0}
                    {@const maxScore = Math.max(
                      ...analyzeResult.tfidf_features.map((f) => f.score),
                    )}
                    <div
                      class="p-6 rounded-2xl bg-white/50 dark:bg-slate-900/50 border border-white/40 dark:border-slate-700/50 shadow-inner"
                    >
                      <p
                        class="text-sm font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-4 text-center lg:text-left"
                      >
                        Top 15 Kata Kunci (TF-IDF)
                      </p>
                      <div class="space-y-3">
                        {#each analyzeResult.tfidf_features as feature}
                          <div class="flex items-center gap-3 group">
                            <span
                              class="w-24 text-xs font-semibold text-slate-700 dark:text-slate-300 truncate text-right group-hover:text-brand-600 dark:group-hover:text-brand-400 transition-colors"
                              title={feature.word}>{feature.word}</span
                            >
                            <div
                              class="flex-1 h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden shadow-inner flex"
                            >
                              <div
                                class="h-full bg-gradient-to-r from-brand-400 to-indigo-500 rounded-full transition-all duration-1000 ease-out"
                                style="width: {(feature.score / maxScore) *
                                  100}%;"
                              ></div>
                            </div>
                            <span
                              class="w-10 text-[10px] text-slate-500 font-mono text-left"
                              >{feature.score.toFixed(3)}</span
                            >
                          </div>
                        {/each}
                      </div>
                    </div>
                  {/if}
                </div>
              {/if}
            </div>
          </div>
        {/if}
      </main>
    </div>
  </div>
{/if}
