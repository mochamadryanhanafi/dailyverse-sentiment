const BASE = import.meta.env.VITE_API_URL ?? '/api'

async function request(path, options = {}) {
  const isFormData = options.body instanceof FormData
  const headers = { ...options.headers }
  if (!isFormData && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
  }

  const token = localStorage.getItem('token')
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  health: {
    server: () => request('/health/'),
    database: () => request('/health/db'),
  },
  auth: {
    google: (token) => {
      return request('/auth/google', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token })
      })
    },
    me: () => request('/auth/me'),
  },
  nlp: {
    exportSentences: (threshold = 0.8) =>
      `${BASE}/nlp/export-sentences?threshold=${threshold}`,
    analyze: (text) =>
      request('/nlp/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      })
  },
  preprocessing: {
    stats: () => request('/preprocessing/stats'),
    runArticles: (force = false, batchSize = 100) =>
      request(`/preprocessing/run?force=${force}&batch_size=${batchSize}`, { method: 'POST' }),
    runStream: (force = false, batchSize = 100) =>
      new EventSource(`${BASE}/preprocessing/run/stream?force=${force}&batch_size=${batchSize}`),
    downloadArticleCsvNoSentimentUrl: `${BASE}/preprocessing/articles/download-csv-no-sentiment`,
    extractSentencesStream: (jaccardThreshold = 0.95) =>
      new EventSource(`${BASE}/preprocessing/extract-sentences/stream?jaccard_threshold=${jaccardThreshold}`),
    downloadPdfUrl: `${BASE}/preprocessing/sentences/download-pdf`,
    downloadCsvUrl: `${BASE}/preprocessing/sentences/download-csv`,
    downloadGroundtruthCsvUrl: (onlyValidated = true) =>
      `${BASE}/preprocessing/sentences/download-groundtruth-csv?only_validated=${onlyValidated}`,
    downloadUnlabeledCsvUrl: `${BASE}/preprocessing/sentences/download-unlabeled-csv`,
    downloadLabeledAsBlankCsvUrl: `${BASE}/preprocessing/sentences/download-labeled-as-blank-csv`,
    downloadStepCsvUrl: (step = 'final') => `${BASE}/preprocessing/sentences/download-step-csv?step=${step}`,
    reset: () => request('/preprocessing/reset', { method: 'POST' }),
    syncSentiment: () => request('/preprocessing/sync-sentiment', { method: 'POST' }),
    autoSplitUnannotated: () => request('/preprocessing/auto-split-unannotated', { method: 'POST' }),
    preview: (limit = 20, offset = 0, status = 'done', onlyValidated = false) => {
      const params = new URLSearchParams({ limit, offset, status, only_validated: onlyValidated })
      return request(`/preprocessing/preview?${params.toString()}`)
    },
    uploadAnnotatedPdf: (file, onEvent) => {
      // Returns an AbortController; call .abort() to cancel
      const controller = new AbortController()
      const token = localStorage.getItem('token')
      const headers = token ? { Authorization: `Bearer ${token}` } : {}
      const formData = new FormData()
      formData.append('file', file)

      ;(async () => {
        try {
          const res = await fetch(`${BASE}/preprocessing/sentences/upload-annotated-pdf`, {
            method: 'POST',
            headers,
            body: formData,
            signal: controller.signal,
          })
          if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
            onEvent({ event: 'error', detail: err.detail || 'Upload gagal' })
            return
          }
          const reader = res.body.getReader()
          const decoder = new TextDecoder()
          let buffer = ''
          while (true) {
            const { done, value } = await reader.read()
            if (done) break
            buffer += decoder.decode(value, { stream: true })
            const lines = buffer.split('\n')
            buffer = lines.pop() // keep incomplete line
            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const data = JSON.parse(line.slice(6))
                  onEvent(data)
                } catch {}
              }
            }
          }
        } catch (e) {
          if (e.name !== 'AbortError') {
            onEvent({ event: 'error', detail: e.message })
          } else {
            onEvent({ event: 'cancelled' })
          }
        }
      })()

      return controller
    },
    uploadAnnotatedCsv: (file) => {
      const formData = new FormData()
      formData.append('file', file)
      return request('/preprocessing/sentences/upload-annotated-csv', {
        method: 'POST',
        body: formData,
      })
    },
    tfidf: (topN = 20, sentimentFilter = 'all') => {
      const params = new URLSearchParams({ top_n: topN, sentiment_filter: sentimentFilter })
      return request(`/preprocessing/tfidf?${params.toString()}`)
    },
    downloadTfidfCsvUrl: (topN = 100, sentimentFilter = 'all') => {
      const params = new URLSearchParams({ top_n: topN, sentiment_filter: sentimentFilter })
      return `${BASE}/preprocessing/tfidf/download-csv?${params.toString()}`
    },
  },

  evaluation: {
    uploadModel: (tfidfFile, logregFile, pipelineFile = null) => {
      const formData = new FormData()
      if (pipelineFile) {
        formData.append('pipeline_file', pipelineFile)
      } else {
        formData.append('tfidf_file', tfidfFile)
        formData.append('logreg_file', logregFile)
      }
      return request('/evaluation/upload-model', {
        method: 'POST',
        body: formData,
      })
    },
    runStream: (limit = 0, includeMismatches = true, onlyValidated = true) => {
      const params = new URLSearchParams({
        limit,
        include_mismatches: includeMismatches,
        only_validated: onlyValidated,
      })
      return new EventSource(`${BASE}/evaluation/run/stream?${params.toString()}`)
    },
  },

  training: {
    train: (testSize = 0.2) => {
      return request(`/training/train?test_size=${testSize}`, {
        method: 'POST'
      })
    }
  },

  ingestion: {
    uploadCsv: async (file) => {
      const formData = new FormData()
      formData.append('file', file)
      const token = localStorage.getItem('token')
      const headers = token ? { Authorization: `Bearer ${token}` } : {}
      const res = await fetch(`${BASE}/ingestion/upload-csv`, {
        method: 'POST',
        headers,
        body: formData,
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Upload failed')
      }
      return res.json()
    }
  },

  scraper: {
    stats: (filters = {}) => {
      const params = new URLSearchParams()
      if (filters.source) params.append('source', filters.source)
      if (filters.sentiment) params.append('sentiment', filters.sentiment)
      return request(`/scraper/articles/stats?${params.toString()}`)
    },
    articles: (limit = 100, offset = 0, filters = {}) => {
      const params = new URLSearchParams({ limit, offset })
      if (filters.source) params.append('source', filters.source)
      if (filters.startDate) params.append('start_date', filters.startDate)
      if (filters.endDate) params.append('end_date', filters.endDate)
      if (filters.sortOrder) params.append('sort_order', filters.sortOrder)
      return request(`/scraper/articles?${params.toString()}`)
    },
    exportArticlesUrl: () => `${BASE}/scraper/articles/export`,
    run: (payload) =>
      request('/scraper/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }),
    runStream: (payload) =>
      new EventSource(`${BASE}/scraper/run/stream?${new URLSearchParams({
        start_year: payload.start_year,
        end_year: payload.end_year,
        total_target: payload.total_target,
      })}`),
    uploadCsv: (file) => {
      const formData = new FormData()
      formData.append('file', file)
      return request('/scraper/upload', {
        method: 'POST',
        body: formData
      })
    }
  },
}
