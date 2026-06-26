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
  let googleButtonReady = false;
  let googleScriptError = false;

  // Set Google Client ID
  const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID;

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
  let sentenceStats = { total: 0, validated: 0 };

  $: annotatedArticlesCount = totalArticles - (sentimentStats.find(s => s.sentiment === 'Belum Dianotasi' || s.sentiment === 'None')?.count || 0);
  $: annotationCoverage = totalArticles > 0 ? Math.round((annotatedArticlesCount / totalArticles) * 100) : 0;
  $: sentenceValidationRate = sentenceStats.total > 0 ? Math.round((sentenceStats.validated / sentenceStats.total) * 100) : 0;
  $: topSource = sourceStats && sourceStats.length > 0
    ? sourceStats.reduce((top, item) => item.count > top.count ? item : top, sourceStats[0])
    : null;
  $: dominantSentiment = sentimentStats && sentimentStats.length > 0
    ? sentimentStats
        .filter(s => s.sentiment && s.sentiment !== 'None' && s.sentiment !== 'Belum Dianotasi')
        .reduce((top, item) => !top || item.count > top.count ? item : top, null)
    : null;

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
  let articlePrepRunning = false;
  let articlePrepForce = false;
  let articlePrepBatchSize = 100;
  let articlePrepMessage = "";

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
  let annotatedCsvFile = null;
  let annotatedPdfUploading = false;
  let annotatedCsvUploading = false;
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
  // Statistik Validasi PDF
  let pdfValidationStats = null; // { total, validated, not_validated, by_sentiment, validated_by_sentiment }

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
  let evalError = '';
  let evalEventSource = null;
  let evalTfidfFile = null;
  let evalLogregFile = null;
  let evalPipelineFile = null;
  let evalModelName = "";
  let evalModelDesc = "";
  let evalModelUploading = false;
  let evalModelMessage = "";
  let evalOnlyValidated = true;
  let mlModels = [];
  let showUploadModelModal = false;
  let evalUploadType = 'pipeline'; // 'pipeline' atau 'separate'

  function buildChartYears(stats) {
    const allYears = new Set(stats.map(s => Number(s.year)).filter(Number.isFinite));
    if (allYears.size === 0) return [];
    const sorted = Array.from(allYears).sort((a, b) => a - b);
    const min = sorted[0];
    const max = sorted[sorted.length - 1];
    const range = [];
    for (let y = min; y <= max; y++) {
      range.push(y);
    }
    return range;
  }

  $: sourceChartYears = buildChartYears(yearSourceStats);
  $: sentimentChartYears = buildChartYears(yearSentimentStats);

  const navItems = [
    { id: "dashboard", label: "Dashboard" },
    { id: "ingestion", label: "Ingesti Data" },
    { id: "articles", label: "Artikel" },
    { id: "preprocessing", label: "Preprocessing" },
    { id: "tfidf", label: "Analisis TF-IDF" },
    { id: "evaluasi", label: "Evaluasi Model" },
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

  function handleLocalLogin() {
    localStorage.removeItem("token");
    userProfile = {
      username: "Local Demo",
      email: "local-demo@dailyverse.test",
      role: "superadmin",
      picture: null,
    };
    isLoggedIn = true;
    loginError = "";
    checkHealth();
    loadArticles();
    loadStats();
  }

  // --- Ingestion ---
  let csvFile = null;
  let uploadingCsv = false;
  let uploadMessage = "";
  let syncLoading = false;

  async function handleIngestionCsvUpload() {
    if (!csvFile) return;
    uploadingCsv = true;
    uploadMessage = "Mengunggah dan memvalidasi...";
    try {
      const res = await api.ingestion.uploadCsv(csvFile);
      uploadMessage = `Berhasil! ${res.articles_inserted} baris CSV masuk database. Data lama sudah dihapus.`;
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
        fetchModels();
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
      if (window.google && GOOGLE_CLIENT_ID) {
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
        googleButtonReady = true;
      } else {
        googleScriptError = true;
      }
    };
    script.onerror = () => {
      googleScriptError = true;
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
      const prep = await api.preprocessing.stats();
      sentenceStats = {
        total: prep.total || 0,
        validated: prep.validated || 0,
      };
    } catch { 
      sourceStats = [];
      sentimentStats = [];
      yearSourceStats = [];
      yearSentimentStats = [];
      sentenceStats = { total: 0, validated: 0 };
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

  async function runArticlePreprocessing() {
    if (articlePrepRunning) return;
    articlePrepRunning = true;
    articlePrepMessage = "";
    try {
      const result = await api.preprocessing.runArticles(
        articlePrepForce,
        articlePrepBatchSize,
      );
      articlePrepMessage = `Berhasil memproses ${result.processed.toLocaleString("id-ID")} artikel. Dilewati: ${result.skipped.toLocaleString("id-ID")}. Total artikel terproses: ${result.total_preprocessed.toLocaleString("id-ID")}.`;
      await loadStats();
    } catch (e) {
      articlePrepMessage = `Gagal preprocessing artikel: ${e.message}`;
    } finally {
      articlePrepRunning = false;
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
        true,
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
    const icon = type === 'error' ? 'ERR' : type === 'warn' ? 'WARN' : type === 'success' ? 'OK' : 'INFO';
    uploadLogs = [...uploadLogs, { ts, icon, msg, type }];
  }

  async function handleSyncSentiment() {
    try {
      syncLoading = true;
      const res = await api.preprocessing.syncSentiment();
      console.log(res.message);
      await loadStats();
      await loadArticles();
    } catch (err) {
      console.error(err);
      alert("Gagal sinkronisasi sentimen");
    } finally {
      syncLoading = false;
    }
  }

  async function handleAnnotatedPdfUpload() {
    if (!annotatedPdfFile) return;
    uploadLogs = [];
    annotatedPdfUploading = true;
    annotatedPdfMessage = '';
    annotatedPdfResult = null;
    pdfValidationStats = null;
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
      if (ev.event === 'ocr_start') {
        uploadPhase = 'ocr';
        addUploadLog(`PDF scan terdeteksi. Menjalankan OCR (proses lebih lama)…`, 'warn');

      } else if (ev.event === 'parsed') {
        uploadPhase = 'deleting';
        uploadTotal = ev.total_parsed;
        const modeLabel = uploadPhase === 'ocr' ? ' [via OCR]' : '';
        addUploadLog(`PDF terparsing${modeLabel}: ${ev.total_parsed} baris ditemukan`, 'info');
        // Simpan statistik validasi dari PDF
        if (ev.pdf_stats) {
          pdfValidationStats = ev.pdf_stats;
          addUploadLog(`Tervalidasi: ${ev.pdf_stats.validated} dari ${ev.total_parsed} baris`, 'info');
        }
      } else if (ev.event === 'deleting') {
        uploadPhase = 'deleting';
        addUploadLog('Menghapus data ekstraksi lama…', 'info');

      } else if (ev.event === 'deleted') {
        uploadPhase = 'inserting';
        addUploadLog(`Data lama dihapus: ${ev.deleted_count} kalimat`, 'info');

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
        // Update statistik validasi dari done event (lebih lengkap)
        if (ev.pdf_stats) {
          pdfValidationStats = ev.pdf_stats;
        }
        addUploadLog(`Insert: ${ev.inserted} kalimat`, 'success');
        if (ev.skipped > 0) addUploadLog(`Dilewati: ${ev.skipped} (tdk ditemukan: ${ev.not_found ?? 0})`, 'warn');
        if (ev.validated_count !== undefined) addUploadLog(`Tervalidasi (kolom V): ${ev.validated_count} | Belum: ${ev.not_validated_count ?? 0}`, 'success');
        addUploadLog(`Selesai! Total baris PDF: ${ev.total_parsed}`, 'success');
        annotatedPdfUploading = false;
        uploadAbortController = null;
        loadPrepStats();
        loadExtractedSentencesPreview();
        loadStats();
        loadArticles();

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

  async function handleAnnotatedCsvUpload() {
    if (!annotatedCsvFile) return;
    uploadLogs = [];
    annotatedCsvUploading = true;
    annotatedPdfMessage = '';
    annotatedPdfResult = null;
    pdfValidationStats = null;

    addUploadLog(`Mulai upload CSV: ${annotatedCsvFile.name} (${(annotatedCsvFile.size/1024).toFixed(1)} KB)`);
    addUploadLog('Mengirim CSV anotasi final ke server…');

    const fileToUpload = annotatedCsvFile;
    annotatedCsvFile = null;

    try {
      const res = await api.preprocessing.uploadAnnotatedCsv(fileToUpload);
      annotatedPdfResult = res;
      annotatedPdfMessage = res.message;
      pdfValidationStats = res.pdf_stats;
      addUploadLog(`Insert: ${res.inserted} kalimat`, 'success');
      if (res.skipped > 0) addUploadLog(`Dilewati: ${res.skipped}`, 'warn');
      addUploadLog(`Tervalidasi: ${res.validated_count} | Belum: ${res.not_validated_count}`, 'success');
      await loadPrepStats();
      await loadExtractedSentencesPreview();
      await loadStats();
      await loadArticles();
    } catch (e) {
      annotatedPdfMessage = `Gagal: ${e.message}`;
      addUploadLog(`GAGAL: ${e.message}`, 'error');
    } finally {
      annotatedCsvUploading = false;
    }
  }

  function cancelUpload() {
    if (uploadAbortController) {
      uploadAbortController.abort();
      uploadAbortController = null;
    }
  }

  function runEvaluation(onlyValidated = true, allowFallback = true) {
    if (evalRunning) return;
    evalRunning = true;
    evalMetrics = null;
    evalMismatches = [];
    evalError = '';
    evalProgress = 0;
    evalTotal = 0;
    evalCurrentText = '';

    evalEventSource = api.evaluation.runStream(0, true, onlyValidated);

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
        evalCurrentText = `Error: ${data.detail}`;
        evalError = data.detail || 'Evaluasi model gagal.';
        evalEventSource.close();
        evalEventSource = null;
        if (allowFallback && onlyValidated && String(data.detail || '').toLowerCase().includes('divalidasi')) {
          evalModelMessage = 'Model berhasil diupload. Data tervalidasi belum tersedia, evaluasi dilanjutkan memakai semua data berlabel.';
          runEvaluation(false, false);
        }
      }
    };
    evalEventSource.onerror = () => {
      evalRunning = false;
      evalError = 'Koneksi evaluasi terputus. Coba jalankan ulang evaluasi.';
      evalEventSource?.close();
      evalEventSource = null;
    };
  }

  function stopEvaluation() {
    evalEventSource?.close();
    evalEventSource = null;
    evalRunning = false;
    evalError = 'Evaluasi dibatalkan.';
  }

  async function fetchModels() {
    try {
      mlModels = await api.evaluation.models();
    } catch (e) {
      console.error("Gagal memuat daftar model:", e);
    }
  }

  async function setActiveModel(id) {
    try {
      await api.evaluation.updateModel(id, { is_active: true });
      await fetchModels();
    } catch (e) {
      alert(`Gagal set model aktif: ${e.message}`);
    }
  }

  async function deleteModel(id) {
    if (!confirm("Apakah Anda yakin ingin menghapus model ini?")) return;
    try {
      await api.evaluation.deleteModel(id);
      await fetchModels();
    } catch (e) {
      alert(`Gagal hapus model: ${e.message}`);
    }
  }

  async function uploadEvaluationModel() {
    if (!evalModelName) {
      alert("Nama model wajib diisi.");
      return;
    }
    if (!evalPipelineFile && (!evalTfidfFile || !evalLogregFile)) return;
    evalModelUploading = true;
    evalModelMessage = "";
    try {
      const res = await api.evaluation.uploadModel(evalModelName, evalModelDesc, evalTfidfFile, evalLogregFile, evalPipelineFile);
      evalModelMessage = res.message || "Model berhasil diupload.";
      evalTfidfFile = null;
      evalLogregFile = null;
      evalPipelineFile = null;
      evalModelName = "";
      evalModelDesc = "";
      showUploadModelModal = false;
      await fetchModels();
    } catch (e) {
      evalModelMessage = `Gagal upload model: ${e.message}`;
    } finally {
      evalModelUploading = false;
    }
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
          `Selesai. Diproses: ${data.processed}, Dilewati: ${data.skipped}, Total terproses: ${data.total_preprocessed}`,
        ];
        await loadPrepStats();
        await loadPrepPreview();
      } else if (data.event === "error") {
        prepLogs = [...prepLogs, `Error: ${data.detail}`];
        prepRunning = false;
        es.close();
      }
    };
    es.onerror = () => {
      prepLogs = [...prepLogs, "Koneksi SSE terputus."];
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
      prepLogs = [`Reset ${r.reset} kalimat. Siap diproses ulang.`];
      prepProgress = 0;
      prepTotal = 0;
      prepDone = false;
      prepPreview = null;
      await loadPrepStats();
    } catch (e) {
      prepLogs = [`Reset gagal: ${e.message}`];
    } finally {
      prepResetting = false;
    }
  }
</script>

{#if !isLoggedIn}
  <div class="liquid-bg min-h-screen flex items-center justify-center p-4">
    <div
      class="glass-card overflow-visible p-8 w-full max-w-sm text-center relative z-10 shadow-2xl"
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

        {#if googleScriptError || !googleButtonReady}
          <button
            type="button"
            class="btn-primary w-full shadow-lg shadow-brand-500/30"
            on:click={handleLocalLogin}
          >
            Masuk ke Dashboard
          </button>
        {/if}

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
    class="liquid-bg flex min-h-screen transition-colors duration-300"
  >
    {#if sidebarOpen}
      <button
        type="button"
        aria-label="Tutup sidebar"
        class="fixed inset-0 z-20 bg-black/40 lg:hidden backdrop-blur-sm"
        on:click={() => (sidebarOpen = false)}
      ></button>
    {/if}

    <aside
      class="
    fixed inset-y-0 left-0 z-30 w-64 flex flex-col
    bg-white/40 dark:bg-slate-900/40 backdrop-blur-3xl border-r border-white/50 dark:border-slate-700/50
    shadow-[4px_0_24px_rgba(0,0,0,0.02)] dark:shadow-[4px_0_24px_rgba(0,0,0,0.2)]
    transition-transform duration-300
    {sidebarOpen
        ? 'translate-x-0'
        : '-translate-x-full'} lg:translate-x-0 lg:h-screen lg:bg-transparent lg:border-r lg:border-slate-200/50 lg:dark:border-slate-700/30
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
            class="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 relative overflow-hidden group
            {activeTab === item.id
              ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-950 shadow-sm'
              : 'text-slate-600 dark:text-slate-300 hover:bg-white/50 dark:hover:bg-slate-800/50 border border-transparent'}"
            on:click={() => navigate(item.id)}
          >
            <span class="h-1.5 w-1.5 rounded-full {activeTab === item.id ? 'bg-white dark:bg-slate-950' : 'bg-slate-300 dark:bg-slate-600'}"></span>
            <span class="relative z-10">{item.label}</span>
            {#if item.id === "articles" && totalArticles > 0}
              <span
                class="ml-auto relative z-10 text-[10px] font-bold {activeTab === item.id ? 'bg-white/20 text-white dark:bg-slate-950/10 dark:text-slate-950' : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300'} px-2.5 py-0.5 rounded-full"
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
        <div class="text-[10px] text-center text-slate-400 font-semibold">
          DailyVerse &copy; 2026
        </div>
      </div>
    </aside>

      <div class="flex-1 flex flex-col min-w-0 relative z-10 lg:ml-64">
        <header
        class="fixed top-0 left-0 right-0 lg:left-64 z-40 h-20 shrink-0 flex items-center gap-3 px-4 sm:px-6 lg:px-8 border-b border-white/20 dark:border-slate-700/30 bg-white/80 dark:bg-slate-900/80 backdrop-blur-xl shadow-sm"
      >
        <button
          type="button"
          class="lg:hidden inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-slate-200/70 dark:border-slate-700 bg-white/60 dark:bg-slate-800/60 text-slate-700 dark:text-slate-200 shadow-sm"
          aria-label="Buka menu"
          on:click={() => (sidebarOpen = true)}
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M2 4.75A.75.75 0 012.75 4h14.5a.75.75 0 010 1.5H2.75A.75.75 0 012 4.75zM2 10a.75.75 0 01.75-.75h14.5a.75.75 0 010 1.5H2.75A.75.75 0 012 10zm0 5.25a.75.75 0 01.75-.75h14.5a.75.75 0 010 1.5H2.75a.75.75 0 01-.75-.75z" clip-rule="evenodd" />
          </svg>
        </button>
        <h1
          class="min-w-0 flex-1 truncate font-extrabold text-slate-900 dark:text-white text-base sm:text-xl capitalize drop-shadow-sm"
        >
          {navItems.find((n) => n.id === activeTab)?.label}
        </h1>
        
        <div class="ml-auto flex min-w-0 items-center gap-2 sm:gap-3">
          <!-- Status Items -->
          <div class="hidden md:flex items-center gap-3 px-3 py-1.5 rounded-full bg-white/30 dark:bg-slate-800/50 border border-white/40 dark:border-slate-700/50 shadow-sm shrink-0">
            <div class="flex items-center gap-1.5">
              <span class="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider hidden sm:block">API</span>
              <StatusBadge status={serverStatus} />
            </div>
            <div class="w-px h-4 bg-slate-300 dark:bg-slate-600"></div>
            <div class="flex items-center gap-1.5">
              <span class="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider hidden sm:block">DB</span>
              <StatusBadge status={dbStatus} />
            </div>
            <div class="w-px h-4 bg-slate-300 dark:bg-slate-600"></div>
            <button
              class="text-slate-500 hover:text-brand-500 dark:hover:text-brand-400 transition-colors p-1"
              on:click={checkHealth}
              title="Refresh Status"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd" />
              </svg>
            </button>
          </div>

          <ThemeToggle />

          {#if userProfile}
            <div
              class="flex items-center gap-2 sm:gap-3 bg-white/30 dark:bg-slate-800/50 px-2 sm:px-3 py-1.5 rounded-full border border-white/40 dark:border-slate-700/50 shadow-sm shrink-0"
            >
              {#if userProfile.picture}
                <img
                  src={userProfile.picture}
                  alt="Profile"
                  class="w-7 h-7 sm:w-8 sm:h-8 rounded-full shadow-sm"
                  referrerpolicy="no-referrer"
                />
              {:else}
                <div
                  class="w-7 h-7 sm:w-8 sm:h-8 rounded-full bg-brand-500 text-white flex items-center justify-center font-bold text-sm"
                >
                  {userProfile.username.charAt(0)}
                </div>
              {/if}
              <div class="hidden sm:flex flex-col">
                <span
                  class="text-xs font-bold text-slate-800 dark:text-slate-100 leading-none"
                  >{userProfile.username}</span
                >
                <span
                  class="text-[10px] font-semibold text-brand-600 dark:text-brand-400 capitalize"
                  >{userProfile.role}</span
                >
              </div>
              <div class="hidden sm:block w-px h-6 bg-slate-300 dark:bg-slate-600 mx-1"></div>
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

      <main class="flex-1 p-4 pt-24 sm:p-8 sm:pt-28 scrollbar-thin {userProfile?.role === 'viewer' ? 'viewer-mode' : ''}">
        {#if userProfile?.role === 'viewer'}
          <div class="mb-6 bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300 text-xs px-4 py-3 rounded-lg text-center font-semibold flex items-center justify-center gap-2 max-w-7xl mx-auto shadow-sm">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
            </svg>
            Mode Viewer: Anda hanya dapat melihat data dan tidak dapat melakukan perubahan atau menambah data.
          </div>
        {/if}
        {#if activeTab === "dashboard"}
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

                <a
                  href={api.scraper.exportArticlesUrl()}
                  target="_blank"
                  class="btn-ghost shadow-sm bg-white/50 dark:bg-slate-800/50 border border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-300"
                  title="Unduh artikel dengan kolom sentimen dikosongkan"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clip-rule="evenodd" />
                  </svg>
                  Unduh CSV Artikel
                </a>

                <button
                  class="btn-primary shadow-sm bg-brand-500 hover:bg-brand-600 text-white flex items-center gap-2"
                  on:click={handleSyncSentiment}
                  disabled={syncLoading}
                  title="Cocokkan artikel dengan sentimen kalimat yang sudah dianotasi"
                >
                  {#if syncLoading}
                    <svg class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/></svg>
                  {:else}
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"/></svg>
                  {/if}
                  Sinkronisasi Sentimen
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
                  {articlesError}
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

          <!-- SECTION: Prep Artikel -->
        {:else if activeTab === "prep_articles"}
          <div class="space-y-6 animate-fade-in max-w-4xl mx-auto">
            <div class="glass-card p-6 sm:p-8 space-y-6">
              <div>
                <h2 class="text-2xl font-bold text-slate-900 dark:text-white">
                  Prep Artikel
                </h2>
                <p class="text-sm text-slate-500 dark:text-slate-400 mt-1 max-w-2xl">
                  Proses isi artikel penuh dengan cleaning, stopword otomatis, dan stemming.
                  CSV hasil unduhan memakai struktur artikel, tetapi kolom sentimen dikosongkan.
                </p>
              </div>

              <div class="grid gap-4 sm:grid-cols-2">
                <label class="space-y-2">
                  <span class="text-xs font-bold uppercase tracking-widest text-slate-400">
                    Batch Size
                  </span>
                  <input
                    type="number"
                    min="1"
                    max="500"
                    bind:value={articlePrepBatchSize}
                    class="input-field w-full"
                    disabled={articlePrepRunning}
                  />
                </label>

                <label class="flex items-center gap-3 rounded-lg border border-slate-200 dark:border-slate-800 px-4 py-3">
                  <input
                    type="checkbox"
                    bind:checked={articlePrepForce}
                    disabled={articlePrepRunning}
                  />
                  <span class="text-sm font-semibold text-slate-700 dark:text-slate-300">
                    Proses ulang artikel yang sudah diproses
                  </span>
                </label>
              </div>

              <div class="flex flex-wrap gap-3">
                <button
                  class="btn-primary"
                  on:click={runArticlePreprocessing}
                  disabled={articlePrepRunning}
                >
                  {articlePrepRunning ? "Memproses Artikel..." : "Jalankan Prep Artikel"}
                </button>

                <a
                  href={api.preprocessing.downloadArticleCsvNoSentimentUrl}
                  target="_blank"
                  class="btn-ghost bg-white/50 dark:bg-slate-800/50 border border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-300"
                  title="Unduh hasil preprocessing artikel tanpa sentimen"
                >
                  Unduh CSV Tanpa Sentimen
                </a>
              </div>

              {#if articlePrepMessage}
                <p class="text-sm font-semibold {articlePrepMessage.startsWith('Gagal') ? 'text-red-600 dark:text-red-400' : 'text-emerald-600 dark:text-emerald-400'}">
                  {articlePrepMessage}
                </p>
              {/if}

              <div class="rounded-lg border border-slate-200 dark:border-slate-800 p-4 text-xs text-slate-500 dark:text-slate-400">
                Format CSV: Year, Month, Date, Title, Content, Content_Preprocessing, URL, sentimen, rangkuman, src_origin, src, urutan, ID_Artikel.
              </div>
            </div>
          </div>

          <!-- SECTION: Ingestion -->
        {:else if activeTab === "ingestion"}
          <div class="p-6 md:p-8 space-y-8 animate-fade-in">
            <div
              class="glass-card p-6 sm:p-8 flex flex-col items-center justify-center text-center space-y-6"
            >
              <div>
                <h2 class="text-2xl font-bold text-slate-800 dark:text-white">
                  Ingesti Data
                </h2>
                <p
                  class="text-slate-500 dark:text-slate-400 mt-2 max-w-lg mx-auto leading-relaxed"
                >
                  Unggah dataset hasil <i>scraping</i> dalam format CSV. Setiap upload
                  akan menghapus dataset lama, lalu memasukkan semua baris CSV.
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
                    NLP Mode
                  </p>
                  <p
                    class="text-sm font-bold text-brand-600 dark:text-brand-400 leading-snug"
                  >
                    {prepStats.stemmer}
                  </p>
                  <p class="text-xs text-slate-400 dark:text-slate-500 leading-snug">
                    Stopword: {prepStats.stopword || "Fallback manual"}
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
                    Ekstraksi Kalimat
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
                      for="extract-jaccard-threshold"
                      class="text-[10px] uppercase font-bold text-slate-400 tracking-wider"
                      >Batas Jaccard</label
                    >
                    <input
                      id="extract-jaccard-threshold"
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
                    Data Kalimat Tervalidasi
                  </h3>
                  <p class="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Tabel ini hanya menampilkan kalimat yang sudah valid dan dapat dipakai sebagai ground truth evaluasi/training.
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
                  <strong>{extractedSentencesPreview.total.toLocaleString('id-ID')}</strong> kalimat tervalidasi
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
                            <span class="inline-block px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300 font-bold text-[10px] uppercase tracking-wider">
                              Valid
                            </span>
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
                  <p class="text-sm text-slate-500 dark:text-slate-400">Belum ada kalimat tervalidasi. Unggah CSV anotasi manual terlebih dahulu.</p>
                </div>
              {:else}
                <div class="py-8 text-center">
                  <p class="text-sm text-slate-400 dark:text-slate-500">Klik "Muat Tabel" untuk melihat data kalimat hasil ekstraksi.</p>
                </div>
              {/if}
            </div>

            <!-- Upload CSV Anotasi (sebelum preprocessing) -->
            <div class="glass-card p-6 sm:p-8 space-y-5 border-2 border-dashed border-emerald-300 dark:border-emerald-800 bg-emerald-50/30 dark:bg-emerald-950/10">
              <div class="flex items-start gap-4">
                <div class="flex-1">
                  <h3 class="font-bold text-slate-800 dark:text-white">Unggah CSV Anotasi Manual</h3>
                  <p class="text-sm text-slate-500 dark:text-slate-400 mt-1 leading-relaxed">
                    Unggah CSV final seperti data validasi OCR.
                    <strong class="text-red-600 dark:text-red-400">Seluruh data ekstraksi sebelumnya akan dihapus</strong> dan diganti dengan data unggahan ini sesuai kode artikelnya.
                  </p>
                  <p class="text-xs text-amber-600 dark:text-amber-400 font-semibold mt-2">
                    Kolom CSV: ID_Artikel | Kalimat_Asli | Label_Final | Sentimen_Final | Status_Data.
                  </p>
                </div>
              </div>

              <div class="flex flex-col sm:flex-row items-start sm:items-center gap-4">
                <div class="flex-1 w-full p-4 bg-white/50 dark:bg-slate-800/30 rounded-2xl border border-dashed border-emerald-300 dark:border-emerald-700 hover:border-emerald-500 transition-colors">
                  <p class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-2">File CSV Final</p>
                  <input
                    type="file"
                    accept=".csv"
                    class="w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-emerald-50 file:text-emerald-700 hover:file:bg-emerald-100"
                    on:change={(e) => { annotatedCsvFile = e.target.files[0]; annotatedPdfMessage = ''; annotatedPdfResult = null; uploadLogs = []; }}
                    disabled={annotatedPdfUploading || annotatedCsvUploading}
                  />
                </div>
                <div class="flex gap-2 shrink-0">
                  <button
                    class="btn-primary bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600 shadow-lg shadow-emerald-500/30 whitespace-nowrap"
                    disabled={!annotatedCsvFile || annotatedPdfUploading || annotatedCsvUploading}
                    on:click={handleAnnotatedCsvUpload}
                  >
                    {#if annotatedCsvUploading}
                      <svg class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/></svg>
                      Memproses…
                    {:else}
                      Unggah CSV
                    {/if}
                  </button>
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
                      {#if uploadPhase === 'uploading'}Mengirim &amp; parsing PDF…
                      {:else if uploadPhase === 'ocr'}
                        <span class="text-purple-600 dark:text-purple-400 font-bold">Menjalankan OCR pada PDF scan… (harap tunggu)</span>
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
                  <div>
                    <p class="text-sm font-semibold {annotatedPdfResult ? 'text-emerald-700 dark:text-emerald-300' : 'text-red-600 dark:text-red-400'}">{annotatedPdfMessage}</p>
                    {#if annotatedPdfResult}
                      <div class="flex flex-wrap gap-4 mt-2 text-xs text-slate-500">
                        <span>Diimpor: <strong class="text-emerald-600">{annotatedPdfResult.inserted}</strong></span>
                        <span>Dilewati: <strong class="text-amber-600">{annotatedPdfResult.skipped}</strong></span>
                        {#if annotatedPdfResult.not_found > 0}<span>Tidak ditemukan: <strong class="text-red-500">{annotatedPdfResult.not_found}</strong></span>{/if}
                        <span>Total diparsing: <strong>{annotatedPdfResult.total_parsed}</strong></span>
                      </div>
                    {/if}
                  </div>
                </div>
              {/if}

              <!-- ═══ Statistik Validasi PDF ═══ -->
              {#if pdfValidationStats}
                {@const pct = pdfValidationStats.total > 0 ? Math.round((pdfValidationStats.validated / pdfValidationStats.total) * 100) : 0}
                {@const sentColors = { Positif: { bg: 'bg-emerald-500', light: 'bg-emerald-50 dark:bg-emerald-900/20', border: 'border-emerald-200 dark:border-emerald-800', text: 'text-emerald-700 dark:text-emerald-300' }, Negatif: { bg: 'bg-red-500', light: 'bg-red-50 dark:bg-red-900/20', border: 'border-red-200 dark:border-red-800', text: 'text-red-700 dark:text-red-300' }, Netral: { bg: 'bg-blue-500', light: 'bg-blue-50 dark:bg-blue-900/20', border: 'border-blue-200 dark:border-blue-800', text: 'text-blue-700 dark:text-blue-300' }, 'Tidak Diketahui': { bg: 'bg-slate-400', light: 'bg-slate-50 dark:bg-slate-800/40', border: 'border-slate-200 dark:border-slate-700', text: 'text-slate-600 dark:text-slate-400' } }}
                <div class="rounded-3xl overflow-hidden border border-violet-200 dark:border-violet-800/50 bg-gradient-to-br from-violet-50 to-indigo-50 dark:from-violet-900/10 dark:to-indigo-900/10 shadow-lg">
                  <!-- Header -->
                  <div class="flex items-center gap-3 px-6 py-4 bg-gradient-to-r from-violet-500 to-indigo-600 text-white">
                    <div>
                      <h4 class="font-bold text-base leading-tight">Statistik Data Tervalidasi</h4>
                      <p class="text-violet-200 text-xs mt-0.5">Ringkasan kolom "Validasi" dari PDF yang diunggah</p>
                    </div>
                    <div class="ml-auto text-right">
                      <p class="text-2xl font-extrabold leading-none">{pdfValidationStats.validated}</p>
                      <p class="text-violet-200 text-xs">dari {pdfValidationStats.total} data</p>
                    </div>
                  </div>

                  <div class="p-5 space-y-5">
                    <!-- Summary Cards -->
                    <div class="grid grid-cols-3 gap-3">
                      <div class="rounded-2xl bg-white/70 dark:bg-slate-800/50 border border-slate-200/60 dark:border-slate-700/50 p-4 text-center shadow-sm">
                        <p class="text-3xl font-extrabold text-slate-800 dark:text-white">{pdfValidationStats.total}</p>
                        <p class="text-xs text-slate-500 dark:text-slate-400 mt-1 font-semibold">Total Baris PDF</p>
                      </div>
                      <div class="rounded-2xl bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 p-4 text-center shadow-sm">
                        <p class="text-3xl font-extrabold text-emerald-600 dark:text-emerald-400">{pdfValidationStats.validated}</p>
                        <p class="text-xs text-emerald-600 dark:text-emerald-500 mt-1 font-semibold">Tervalidasi</p>
                        <p class="text-[10px] text-emerald-400 mt-0.5">{pct}% dari total</p>
                      </div>
                      <div class="rounded-2xl bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 p-4 text-center shadow-sm">
                        <p class="text-3xl font-extrabold text-amber-600 dark:text-amber-400">{pdfValidationStats.not_validated}</p>
                        <p class="text-xs text-amber-600 dark:text-amber-500 mt-1 font-semibold">Belum divalidasi</p>
                        <p class="text-[10px] text-amber-400 mt-0.5">{100 - pct}% dari total</p>
                      </div>
                    </div>

                    <!-- Progress Bar Validasi -->
                    <div class="space-y-2">
                      <div class="flex justify-between text-xs font-semibold">
                        <span class="text-slate-600 dark:text-slate-400">Progres Validasi</span>
                        <span class="text-violet-600 dark:text-violet-400 font-bold">{pct}%</span>
                      </div>
                      <div class="relative h-5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden shadow-inner">
                        <div
                          class="h-full rounded-full bg-gradient-to-r from-violet-500 to-indigo-500 transition-all duration-700 ease-out flex items-center justify-end pr-2"
                          style="width: {pct}%;"
                        >
                          {#if pct > 10}
                            <span class="text-white text-[10px] font-bold">{pct}%</span>
                          {/if}
                        </div>
                      </div>
                      <div class="flex justify-between text-[10px] text-slate-400">
                        <span>0</span>
                        <span>{pdfValidationStats.total}</span>
                      </div>
                    </div>

                    <!-- Breakdown per Sentimen -->
                    <div>
                      <p class="text-xs font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500 mb-3">Distribusi per Sentimen</p>
                      <div class="space-y-2.5">
                        {#each Object.entries(pdfValidationStats.by_sentiment).filter(([k, v]) => v > 0) as [sent, total]}
                          {@const validated = pdfValidationStats.validated_by_sentiment[sent] || 0}
                          {@const notval = total - validated}
                          {@const sentPct = total > 0 ? Math.round((validated / total) * 100) : 0}
                          {@const colors = sentColors[sent] || sentColors['Tidak Diketahui']}
                          <div class="rounded-2xl {colors.light} border {colors.border} p-3">
                            <div class="flex items-center justify-between mb-2">
                              <div class="flex items-center gap-2">
                                <span class="font-bold text-sm {colors.text}">{sent}</span>
                              </div>
                              <div class="flex items-center gap-3 text-xs">
                                <span class="text-emerald-600 dark:text-emerald-400 font-bold">Valid {validated}</span>
                                <span class="text-slate-400">|</span>
                                <span class="text-amber-500 font-semibold">Belum {notval}</span>
                                <span class="text-slate-400 font-bold">= {total}</span>
                              </div>
                            </div>
                            <div class="h-2 bg-white/60 dark:bg-slate-700/50 rounded-full overflow-hidden">
                              <div
                                class="h-full rounded-full {colors.bg} transition-all duration-700 opacity-80"
                                style="width: {sentPct}%;"
                              ></div>
                            </div>
                            <p class="text-right text-[10px] text-slate-400 mt-1">{sentPct}% tervalidasi</p>
                          </div>
                        {/each}
                      </div>
                    </div>

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
                    Preprocessing NLP
                  </h2>
                  <p
                    class="text-sm text-slate-500 dark:text-slate-400 mt-1 leading-relaxed"
                  >
                    Memproses kalimat yang telah diekstrak dari
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
                    for="batchSize">Batch Size (kalimat per batch)</label
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

                <a
                  href={api.preprocessing.downloadGroundtruthCsvUrl(true)}
                  target="_blank"
                  class="btn-ghost bg-white/50 dark:bg-slate-800/50 border border-blue-200 dark:border-blue-800 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/40 shadow-sm flex justify-center items-center gap-1 {prepRunning ? 'opacity-50 pointer-events-none' : ''}"
                  title="Unduh hanya data tervalidasi sebagai ground truth training/evaluasi LogReg"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clip-rule="evenodd" />
                  </svg>
                  Ground Truth Valid
                </a>

                <a
                  href={api.preprocessing.downloadUnlabeledCsvUrl}
                  target="_blank"
                  class="btn-ghost bg-white/50 dark:bg-slate-800/50 border border-amber-200 dark:border-amber-800 text-amber-700 dark:text-amber-300 hover:bg-amber-50 dark:hover:bg-amber-900/30 shadow-sm flex justify-center items-center gap-1 {prepRunning ? 'opacity-50 pointer-events-none' : ''}"
                  title="Unduh kalimat yang belum diberi label sentimen"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clip-rule="evenodd" />
                  </svg>
                  Belum Berlabel
                </a>

                <a
                  href={api.preprocessing.downloadLabeledAsBlankCsvUrl}
                  target="_blank"
                  class="btn-ghost bg-white/50 dark:bg-slate-800/50 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 shadow-sm flex justify-center items-center gap-1 {prepRunning ? 'opacity-50 pointer-events-none' : ''}"
                  title="Unduh kalimat yang sudah berlabel, tetapi label sentimennya dikosongkan"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clip-rule="evenodd" />
                  </svg>
                  Label Dikosongkan
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
                    {#if prepRunning}Sedang memproses…{:else if prepDone}Selesai{:else}Progress{/if}
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
          <div class="space-y-6 animate-fade-in max-w-3xl mx-auto">
            <div class="glass-card p-6 sm:p-8 space-y-6">
              <div class="flex justify-between items-center">
                <div>
                  <h2 class="text-2xl font-bold text-slate-900 dark:text-white">Manajemen Model ML</h2>
                  <p class="text-sm text-slate-500 dark:text-slate-400 mt-1 max-w-2xl">
                    Kelola model evaluasi yang telah disimpan.
                  </p>
                </div>
                <button class="btn-primary" on:click={() => showUploadModelModal = true}>
                  Upload Model Baru
                </button>
              </div>

              {#if mlModels.length > 0}
                <div class="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700 mt-4">
                  <table class="w-full text-sm text-left text-slate-500 dark:text-slate-400">
                    <thead class="text-xs text-slate-700 uppercase bg-slate-50 dark:bg-slate-800 dark:text-slate-300">
                      <tr>
                        <th scope="col" class="px-6 py-3">Nama Model</th>
                        <th scope="col" class="px-6 py-3">Deskripsi</th>
                        <th scope="col" class="px-6 py-3">Status</th>
                        <th scope="col" class="px-6 py-3 text-right">Aksi</th>
                      </tr>
                    </thead>
                    <tbody>
                      {#each mlModels as model}
                        <tr class="bg-white border-b dark:bg-slate-900 dark:border-slate-700">
                          <td class="px-6 py-4 font-medium text-slate-900 whitespace-nowrap dark:text-white">
                            {model.name}
                          </td>
                          <td class="px-6 py-4">
                            {model.description || "-"}
                          </td>
                          <td class="px-6 py-4">
                            {#if model.is_active}
                              <span class="bg-green-100 text-green-800 text-xs font-medium me-2 px-2.5 py-0.5 rounded dark:bg-green-900 dark:text-green-300">Aktif</span>
                            {:else}
                              <span class="bg-slate-100 text-slate-800 text-xs font-medium me-2 px-2.5 py-0.5 rounded dark:bg-slate-700 dark:text-slate-300">Tidak Aktif</span>
                            {/if}
                          </td>
                          <td class="px-6 py-4 text-right space-x-2">
                            {#if !model.is_active}
                              <button class="text-brand-600 dark:text-brand-400 hover:underline text-xs font-bold" on:click={() => setActiveModel(model.id)}>Set Aktif</button>
                            {/if}
                            <button class="text-red-600 dark:text-red-400 hover:underline text-xs font-bold ml-2" on:click={() => deleteModel(model.id)}>Hapus</button>
                          </td>
                        </tr>
                      {/each}
                    </tbody>
                  </table>
                </div>
              {:else}
                <div class="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg text-center text-sm text-slate-500">
                  Belum ada model tersimpan.
                </div>
              {/if}

              <div class="pt-6 border-t border-slate-200 dark:border-slate-700">
                <h3 class="text-lg font-bold text-slate-900 dark:text-white mb-4">Uji Model Aktif</h3>
                <div class="flex flex-col sm:flex-row sm:items-center gap-3">
                  <button
                    class="btn-primary justify-center"
                    on:click={() => runEvaluation()}
                    disabled={evalRunning || mlModels.filter(m => m.is_active).length === 0}
                  >
                    {#if evalRunning}
                      Menghitung Akurasi...
                    {:else}
                      Jalankan Evaluasi
                    {/if}
                  </button>
  
                  {#if evalRunning}
                    <button
                      class="btn-ghost justify-center border border-slate-200 dark:border-slate-800"
                      on:click={stopEvaluation}
                    >
                      Batalkan
                    </button>
                  {/if}
                </div>
              </div>

              {#if evalError && !evalRunning}
                <div class="rounded-lg border border-red-200 dark:border-red-900/60 bg-red-50 dark:bg-red-950/30 px-4 py-3 mt-4">
                  <p class="text-sm font-bold text-red-700 dark:text-red-300">Evaluasi belum bisa ditampilkan</p>
                  <p class="mt-1 text-sm text-red-600 dark:text-red-300">{evalError}</p>
                </div>
              {/if}
            </div>

            <!-- Modal Upload Model -->
            {#if showUploadModelModal}
              <div class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm">
                <div class="bg-white dark:bg-slate-900 rounded-2xl shadow-xl w-full max-w-lg overflow-hidden animate-scale-in">
                  <div class="p-6 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center">
                    <h3 class="text-lg font-bold text-slate-900 dark:text-white">Upload Model Baru</h3>
                    <button class="text-slate-400 hover:text-slate-600" on:click={() => showUploadModelModal = false}>✕</button>
                  </div>
                  <div class="p-6 space-y-4">
                    <label class="space-y-2 block">
                      <span class="text-xs font-bold uppercase tracking-widest text-slate-500">Nama Model *</span>
                      <input type="text" class="input-field w-full px-3 py-2 border rounded-lg dark:bg-slate-800 dark:border-slate-700 dark:text-white" bind:value={evalModelName} placeholder="Misal: Model LogReg V1" />
                    </label>
                    <label class="space-y-2 block">
                      <span class="text-xs font-bold uppercase tracking-widest text-slate-500">Deskripsi</span>
                      <input type="text" class="input-field w-full px-3 py-2 border rounded-lg dark:bg-slate-800 dark:border-slate-700 dark:text-white" bind:value={evalModelDesc} placeholder="Misal: Model terlatih..." />
                    </label>
                    <div class="border-t border-slate-200 dark:border-slate-700 pt-4 mt-2">
                      <p class="text-xs font-medium text-slate-500 mb-4">Pilih Format File Model yang Ingin Diupload:</p>
                      
                      <div class="flex gap-4 mb-4">
                        <label class="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300 cursor-pointer">
                          <input type="radio" bind:group={evalUploadType} value="pipeline" class="text-brand-600 focus:ring-brand-500" />
                          1 File (Pipeline)
                        </label>
                        <label class="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300 cursor-pointer">
                          <input type="radio" bind:group={evalUploadType} value="separate" class="text-brand-600 focus:ring-brand-500" />
                          2 File Terpisah (TF-IDF + LogReg)
                        </label>
                      </div>

                      {#if evalUploadType === 'pipeline'}
                        <label class="space-y-2 block mb-4 animate-fade-in">
                          <span class="text-xs font-bold uppercase tracking-widest text-slate-400">File Pipeline (.pkl)</span>
                          <input
                            type="file" accept=".pkl"
                            class="w-full text-xs text-slate-500 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-slate-100 file:text-slate-700 hover:file:bg-slate-200"
                            on:change={(e) => {evalPipelineFile = e.target.files[0]; evalTfidfFile = null; evalLogregFile = null;}}
                            disabled={evalModelUploading}
                          />
                        </label>
                      {:else}
                        <div class="grid gap-4 sm:grid-cols-2 animate-fade-in">
                          <label class="space-y-2">
                            <span class="text-xs font-bold uppercase tracking-widest text-slate-400">File TF-IDF (.pkl)</span>
                            <input
                              type="file" accept=".pkl"
                              class="w-full text-xs text-slate-500 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-slate-100 file:text-slate-700 hover:file:bg-slate-200"
                              on:change={(e) => {evalTfidfFile = e.target.files[0]; evalPipelineFile = null;}}
                              disabled={evalModelUploading}
                            />
                          </label>
                          <label class="space-y-2">
                            <span class="text-xs font-bold uppercase tracking-widest text-slate-400">File LogReg (.pkl)</span>
                            <input
                              type="file" accept=".pkl"
                              class="w-full text-xs text-slate-500 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-slate-100 file:text-slate-700 hover:file:bg-slate-200"
                              on:change={(e) => {evalLogregFile = e.target.files[0]; evalPipelineFile = null;}}
                              disabled={evalModelUploading}
                            />
                          </label>
                        </div>
                      {/if}
                    </div>
                    
                    {#if evalModelMessage}
                      <p class="text-sm font-semibold {evalModelMessage.startsWith('Gagal') ? 'text-red-600' : 'text-emerald-600'}">
                        {evalModelMessage}
                      </p>
                    {/if}
                  </div>
                  <div class="p-6 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50 flex justify-end gap-3">
                    <button class="btn-ghost px-4 py-2 border border-slate-200 dark:border-slate-700 rounded-lg" on:click={() => showUploadModelModal = false} disabled={evalModelUploading}>Batal</button>
                    <button class="btn-primary px-4 py-2" on:click={uploadEvaluationModel} disabled={evalModelUploading || (!evalModelName) || (!evalPipelineFile && (!evalTfidfFile || !evalLogregFile))}>
                      {evalModelUploading ? 'Menyimpan...' : 'Simpan Model'}
                    </button>
                  </div>
                </div>
              </div>
            {/if}

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
              {@const wrongSentences = evalMismatches.slice(0, 20)}
              <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div class="glass-card p-5">
                  <p class="text-xs font-bold uppercase tracking-widest text-slate-400">Accuracy</p>
                  <p class="mt-2 text-4xl font-black text-brand-600 dark:text-brand-400">
                    {(evalMetrics.accuracy * 100).toFixed(2)}%
                  </p>
                  <p class="text-xs text-slate-400 mt-1">
                    {evalMetrics.correct.toLocaleString('id-ID')} / {evalMetrics.total.toLocaleString('id-ID')} benar
                  </p>
                </div>
                <div class="glass-card p-5">
                  <p class="text-xs font-bold uppercase tracking-widest text-slate-400">Recall</p>
                  <p class="mt-2 text-4xl font-black text-amber-600 dark:text-amber-400">
                    {(evalMetrics.macro_avg.recall * 100).toFixed(2)}%
                  </p>
                  <p class="text-xs text-slate-400 mt-1">macro average</p>
                </div>
                <div class="glass-card p-5">
                  <p class="text-xs font-bold uppercase tracking-widest text-slate-400">Precision</p>
                  <p class="mt-2 text-4xl font-black text-emerald-600 dark:text-emerald-400">
                    {(evalMetrics.macro_avg.precision * 100).toFixed(2)}%
                  </p>
                  <p class="text-xs text-slate-400 mt-1">macro average</p>
                </div>
                <div class="glass-card p-5">
                  <p class="text-xs font-bold uppercase tracking-widest text-slate-400">F1-Score</p>
                  <p class="mt-2 text-4xl font-black text-indigo-600 dark:text-indigo-400">
                    {(evalMetrics.macro_avg.f1 * 100).toFixed(2)}%
                  </p>
                  <p class="text-xs text-slate-400 mt-1">macro average</p>
                </div>
              </div>

              <div class="grid grid-cols-1 lg:grid-cols-2 gap-5">
                <div class="glass-card p-5 sm:p-6 space-y-4">
                  <div>
                    <h3 class="font-bold text-slate-900 dark:text-white">Confusion Matrix</h3>
                    <p class="text-xs text-slate-500 dark:text-slate-400">
                      Baris = label ahli, kolom = prediksi model.
                    </p>
                  </div>
                  {#if evalMetrics.confusion_matrix}
                    {@const cm = evalMetrics.confusion_matrix}
                    {@const labels = evalMetrics.labels}
                    {@const maxVal = Math.max(...cm.flat(), 1)}
                    <div class="overflow-x-auto">
                      <table class="w-full text-xs border-collapse">
                        <thead>
                          <tr>
                            <th class="p-2 text-left text-slate-400">Aktual / Prediksi</th>
                            {#each labels as label}
                              <th class="p-2 text-center font-bold text-slate-600 dark:text-slate-300">{label}</th>
                            {/each}
                          </tr>
                        </thead>
                        <tbody>
                          {#each cm as row, ri}
                            <tr>
                              <td class="p-2 font-bold text-slate-700 dark:text-slate-200">{labels[ri]}</td>
                              {#each row as cell, ci}
                                {@const intensity = cell / maxVal}
                                {@const isCorrect = ri === ci}
                                <td class="p-1">
                                  <div
                                    class="rounded-lg p-3 text-center font-black text-lg"
                                    style="background: {isCorrect ? `rgba(16,185,129,${0.12 + intensity * 0.65})` : `rgba(239,68,68,${0.08 + intensity * 0.45})`};"
                                  >
                                    <span class="{isCorrect ? 'text-emerald-700 dark:text-emerald-200' : 'text-red-700 dark:text-red-200'}">{cell}</span>
                                  </div>
                                </td>
                              {/each}
                            </tr>
                          {/each}
                        </tbody>
                      </table>
                    </div>
                  {/if}
                </div>

                <div class="glass-card p-5 sm:p-6 space-y-4">
                  <div>
                    <h3 class="font-bold text-slate-900 dark:text-white">Recall Per Kelas</h3>
                    <p class="text-xs text-slate-500 dark:text-slate-400">
                      Seberapa banyak label ahli yang berhasil dikenali model.
                    </p>
                  </div>
                  <div class="space-y-3">
                    {#each evalMetrics.per_class as cls}
                      <div>
                        <div class="flex items-center justify-between mb-1">
                          <span class="text-sm font-bold text-slate-700 dark:text-slate-200">{cls.label}</span>
                          <span class="text-xs font-mono text-slate-500">{(cls.recall * 100).toFixed(2)}%</span>
                        </div>
                        <div class="h-2 rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden">
                          <div
                            class="h-full rounded-full {cls.label === 'Positif' ? 'bg-emerald-500' : cls.label === 'Negatif' ? 'bg-red-500' : 'bg-blue-500'}"
                            style="width: {Math.max(cls.recall * 100, 1)}%;"
                          ></div>
                        </div>
                        <p class="text-[11px] text-slate-400 mt-1">
                          support {cls.support.toLocaleString('id-ID')} kalimat
                        </p>
                      </div>
                    {/each}
                  </div>
                </div>
              </div>

              <div class="glass-card p-5 sm:p-6 space-y-4">
                <div>
                  <h3 class="font-bold text-slate-900 dark:text-white">Kalimat Salah</h3>
                  <p class="text-xs text-slate-500 dark:text-slate-400">
                    Kalimat yang label prediksi modelnya berbeda dari label validasi ahli.
                  </p>
                </div>
                {#if wrongSentences.length > 0}
                  <div class="space-y-3">
                    {#each wrongSentences as item}
                      <div class="rounded-lg border border-slate-200 dark:border-slate-800 p-4">
                        <p class="text-sm text-slate-700 dark:text-slate-200 leading-relaxed">{item.text}</p>
                        <div class="mt-3 flex flex-wrap gap-2 text-xs">
                          <span class="rounded-md bg-emerald-100 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 px-2 py-1 font-semibold">
                            Label ahli: {item.true}
                          </span>
                          <span class="rounded-md bg-red-100 dark:bg-red-950/40 text-red-700 dark:text-red-300 px-2 py-1 font-semibold">
                            Prediksi model: {item.pred}
                          </span>
                          <span class="rounded-md bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-300 px-2 py-1 font-semibold">
                            Confidence: {(item.confidence * 100).toFixed(1)}%
                          </span>
                        </div>
                      </div>
                    {/each}
                  </div>
                {:else}
                  <p class="text-sm text-slate-500 dark:text-slate-400">
                    Belum ada kalimat yang salah diprediksi pada sampel mismatch yang diterima.
                  </p>
                {/if}
              </div>

            {:else if !evalRunning}
              <div class="glass-card p-12 flex flex-col items-center gap-3 text-center">
                <p class="text-xl font-bold text-slate-700 dark:text-slate-200">Belum Ada Hasil Akurasi</p>
                <p class="text-sm text-slate-500 dark:text-slate-400 max-w-md">
                  Upload model terlebih dahulu untuk menghitung akurasi terhadap data validasi ahli.
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
                    Analisis TF-IDF
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
                    <label for="tfidf-top-n" class="text-xs font-bold text-slate-500 dark:text-slate-400 whitespace-nowrap">Top-N:</label>
                    <input
                      id="tfidf-top-n"
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
                      Top Term Keseluruhan (TF-IDF Global)
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
        {/if}
      </main>
    </div>
  </div>
{/if}

<style>
  :global(.viewer-mode .btn-primary),
  :global(.viewer-mode .btn-secondary),
  :global(.viewer-mode input[type="file"]),
  :global(.viewer-mode select) {
    opacity: 0.5;
    pointer-events: none;
    cursor: not-allowed;
  }
</style>
