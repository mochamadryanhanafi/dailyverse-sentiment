.PHONY: dev dev-down prod-up prod-down deploy logs logs-prod clean

# ==========================================
# COMMANDS UNTUK LOKAL (LAPTOP)
# ==========================================

# Menjalankan aplikasi di lokal (Development)
dev:
	docker compose -f docker-compose.yml up -d --build

# Mematikan aplikasi di lokal
dev-down:
	docker compose -f docker-compose.yml down

# Mengirim kode terbaru ke VPS (Auto commit & push)
deploy:
	git add .
	git commit -m "Auto deploy update from Makefile" || true
	git push
	@echo "======================================================="
	@echo "Kode berhasil di-push! Sekarang login ke VPS dan jalankan:"
	@echo "git pull && make prod-up"
	@echo "======================================================="

# ==========================================
# COMMANDS UNTUK SERVER (VPS)
# ==========================================

# Menjalankan aplikasi di production (VPS)
prod-up:
	docker compose -f docker-compose.prod.yml down
	docker compose -f docker-compose.prod.yml up -d --build

# Mematikan aplikasi di production (VPS)
prod-down:
	docker compose -f docker-compose.prod.yml down

# ==========================================
# COMMANDS UMUM
# ==========================================

# Melihat log aplikasi di lokal
logs:
	docker compose -f docker-compose.yml logs -f

# Melihat log aplikasi di production
logs-prod:
	docker compose -f docker-compose.prod.yml logs -f

# Menghapus semua container dan volume (HATI-HATI: Data database akan hilang!)
clean:
	docker compose -f docker-compose.yml down -v
	docker compose -f docker-compose.prod.yml down -v
