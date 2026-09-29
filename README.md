# Görev Tanımı Benzerlik — Streamlit Cloud (mock) demo

Herkese açık **Streamlit Cloud** için hazırlanmış, tek dosyalık, self-contained demo sürümü.

## Tam sürümden farkları

| | Kurum içi tam sürüm (`arayuz/`) | Bu cloud demo |
|---|---|---|
| Veri | PositionDefinition (SQL) / mock | **Sadece mock** |
| Kavram etiketleme | kurum içi LLM (`oss-120b`) + kural yedeği | **Sadece kural tabanlı (LLM yok, ağ çağrısı yok)** |
| Geri bildirim | SQLite (`feedback.db`) | **Oturum belleği** + CSV indir (Cloud'da disk kalıcı değil) |
| Ontoloji | `kavram_ontolojisi_llm.json` (dosya) | Oturumda düzenle + JSON indir |

4 sekme (Karşılaştırma / Rol–Kavram Görünümü / Kavram Ontolojisi / Geri Bildirim) ve akış tam sürümle aynıdır. Karşılaştırmada %30+ çiftler "incelenecek (farklı pozisyon)" ve "aynı pozisyon kıdem/seviye versiyonları (beklenen)" olarak ayrılır.

**Karşılaştırma kaynağı (3 seçenek):** Karşılaştırma ekranında radio ile:
- **Örnek pozisyonlar** — gömülü örnek görevlerden seç.
- **Metin yapıştır** — her görevin *özet + sorumluluklar* metnini doğrudan yapıştır (2+ görev).
- **Dosya yükle (PDF/DOCX)** — 2+ **PDF** veya **DOCX** yükle; metin `pypdf` / `python-docx` ile çıkarılır.

Hepsinde karşılaştırma **LLM'siz, kural tabanlı** kavram etiketlemesiyle yapılır. (Taranmış/görüntü PDF'lerde metin çıkmaz.)

> Not: "Örnek pozisyonlar" verisi gerçek `.docx`/tablo örneklerinden **çıkarılmadı**; domaine uygun, elle yazılmış temsili örneklerdir (demo için).

**Yapay zeka yorumu (opsiyonel):** Karşılaştırma ve Rol–Kavram ekranlarında "🤖 Yapay zeka yorumu al" butonu vardır. Cloud'da LLM varsayılan kapalıdır; Streamlit **Secrets**'a aşağıdaki gibi ekleyerek etkinleştirilebilir:

```toml
[llm]
base_url = "https://<llm-endpoint>/v1"
model = "<model-adi>"
api_key = "<anahtar>"   # gerekmiyorsa boş
```

## Yerelde çalıştırma

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Streamlit Cloud'a deploy

1. Bu klasörü (ya da tüm repoyu) bir **GitHub reposuna** koy.
2. [share.streamlit.io](https://share.streamlit.io) → **New app** → repoyu seç.
3. **Main file path:** `arayuz-cloud/streamlit_app.py` (repo kökündeyse `streamlit_app.py`).
4. Deploy. Ek "secrets" veya ortam değişkeni gerekmez — her şey mock/kural tabanlı.

## Notlar

- İnternet gerektirmez; hiçbir dış servise bağlanmaz (kurum içi LLM bu sürümde kapalı).
- Geri bildirimler kalıcı değildir (Cloud yeniden başlarsa sıfırlanır) — kalıcılık için CSV indir veya kurum içi tam sürümü kullan.
- Kavram ontolojisini düzenleyip **indirip** repodaki dosyayla değiştirerek varsayılanı güncelleyebilirsin.
