# DailyVerse Sentiment

Dashboard analisis sentimen berita ekonomi Indonesia berbasis FastAPI, Svelte, PostgreSQL, TF-IDF, dan Logistic Regression.

Project ini mengelola data artikel berita, mengekstrak kalimat ekonomi yang relevan, melakukan preprocessing Bahasa Indonesia, menerima anotasi manual, melatih model klasifikasi sentimen, dan mengevaluasi hasil prediksi model terhadap label manual.

## Arsitektur

- `backend/` - FastAPI API server.
- `frontend/` - Svelte + Vite dashboard.
- `db/` - inisialisasi dan migration SQL PostgreSQL.
- `backend/tfidf.pkl` - vectorizer TF-IDF tersimpan.
- `backend/logreg.pkl` - model Logistic Regression tersimpan.

## Fitur Utama

- Autentikasi Google OAuth dan token JWT.
- Upload dataset artikel CSV dengan mode `replace` atau `append`.
- Dashboard statistik artikel berdasarkan sumber, tahun, dan sentimen.
- Ekstraksi kalimat dari artikel dengan filter topik ekonomi dan deduplikasi Jaccard.
- Preprocessing teks: cleaning, case folding, stopword removal, dan stemming Sastrawi.
- Export kalimat untuk anotasi manual.
- Upload PDF hasil anotasi manual.
- Analisis TF-IDF.
- Training model TF-IDF + Logistic Regression.
- Evaluasi model dengan confusion matrix, accuracy, precision, recall, dan F1-score.
- Analisis sentimen realtime untuk teks baru.

## Cara Menjalankan

Salin konfigurasi contoh jika diperlukan:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Jalankan semua service dengan Docker Compose:

```bash
docker compose up --build
```

URL default:

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- Dokumentasi API: `http://localhost:8000/docs`
- PostgreSQL: `localhost:5432`

Untuk menjalankan hanya database:

```bash
docker compose up db
```

## Konfigurasi Penting

Backend memakai environment variable berikut:

- `DATABASE_URL`
- `SECRET_KEY`
- `GOOGLE_CLIENT_ID`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `DEFAULT_USER_ROLE`

Frontend memakai:

- `VITE_API_URL`
- `VITE_API_TARGET`
- `VITE_GOOGLE_CLIENT_ID`

Untuk production, jangan gunakan nilai default `SECRET_KEY`.

## Database

Tabel utama:

- `articles` - data artikel berita.
- `article_sentences` - kalimat hasil ekstraksi dari artikel.
- `users` - data user login.
- `audit_logs` - catatan aksi penting seperti upload dataset.

`db/init.sql` dipakai saat database volume pertama kali dibuat. Jika database sudah pernah dibuat, jalankan migration manual:

```bash
docker compose exec db psql -U dailyverse -d dailyverse_db -f /migrations/001_sync_article_pipeline_schema.sql
```

## Alur Data

1. Dataset artikel masuk lewat CSV atau scraper.
2. Artikel disimpan di tabel `articles`.
3. Sistem mengekstrak kalimat dari artikel yang relevan dengan topik ekonomi.
4. Kalimat dideduplikasi menggunakan Jaccard similarity.
5. Kalimat disimpan di `article_sentences`.
6. Kalimat dipreprocessing.
7. Kalimat dianotasi manual melalui PDF.
8. Label manual dipakai untuk training dan evaluasi model.
9. Model tersimpan dipakai untuk prediksi realtime.

## Metodologi NLP

Pipeline preprocessing:

1. Cleaning: menghapus HTML, URL, tanda baca, angka, dan spasi berlebih.
2. Case folding: mengubah teks menjadi huruf kecil.
3. Token filtering: menghapus stopword Bahasa Indonesia dan token terlalu pendek.
4. Stemming: mengubah kata ke bentuk dasar menggunakan Sastrawi.

Ekstraksi kalimat:

- Artikel harus mengandung kata kunci ekonomi.
- Kalimat terlalu pendek atau mengandung pola non-berita dibuang.
- Kalimat yang terlalu mirip dibuang dengan Jaccard similarity.

Model:

- Pembobotan fitur: TF-IDF.
- Klasifikasi: Logistic Regression.
- Label: `Positif`, `Negatif`, `Netral`.

## Endpoint Penting

- `POST /auth/google`
- `GET /auth/me`
- `POST /ingestion/upload-csv?mode=replace`
- `POST /ingestion/upload-csv?mode=append`
- `GET /scraper/articles`
- `GET /scraper/articles/stats`
- `GET /preprocessing/extract-sentences/stream`
- `GET /preprocessing/run/stream`
- `POST /preprocessing/sentences/upload-annotated-pdf`
- `GET /preprocessing/tfidf`
- `POST /training/train`
- `GET /evaluation/run/stream`
- `POST /nlp/analyze`

## Catatan Pengembangan

- Gunakan mode `replace` saat ingin mengganti dataset utama sepenuhnya.
- Gunakan mode `append` saat ingin menambahkan data baru tanpa menghapus dataset lama. Artikel dengan URL atau judul yang sama tetap akan disimpan sebagai baris terpisah.
- Jika model baru dilatih, file `backend/tfidf.pkl` dan `backend/logreg.pkl` akan diperbarui.
- Jangan commit credential production ke repository.
