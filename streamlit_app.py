# -*- coding: utf-8 -*-
"""
streamlit_app.py — Görev Tanımı Benzerlik Arayüzü · STREAMLIT CLOUD (mock) sürümü

Bu sürüm herkese açık Streamlit Cloud'da demo için tasarlandı; kurum içi
sunucudaki tam sürümden farkları:
  • Veri: yalnızca MOCK (SQL / PositionDefinition yok).
  • LLM YOK: kavram etiketleme kural tabanlı — hiçbir ağ çağrısı yapılmaz.
  • Kalıcı backend yok: geri bildirimler oturum (session) belleğinde tutulur ve
    CSV olarak indirilebilir. (Streamlit Cloud'da disk kalıcı değildir.)
  • Ontoloji düzenlemeleri oturumda geçerli olur ve JSON olarak indirilebilir.

Tek dosyadır (core/db bağımlılığı yoktur) — Streamlit Cloud'a doğrudan deploy edilir.
Çalıştırma:  streamlit run streamlit_app.py
"""
from __future__ import annotations

import io
import json
import re
import ssl
from itertools import combinations
from datetime import datetime
from urllib.request import Request, urlopen

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Görev Tanımı Benzerlik (Demo)",
                   layout="wide")

ESIK_VARSAYILAN = 0.30

# ============================================================================
# KAVRAM ONTOLOJİSİ (varsayılan) + kurallar
# ============================================================================
CONCEPTS_VARSAYILAN = {
 "C1":"Müşteri/Portföy Yönetimi", "C2":"Satış & Hedef/Gelir Odaklılığı",
 "C3":"Mevzuat & Uyum", "C4":"Performans Takibi & Yönetsel Raporlama",
 "C5":"Bütçe Planlama", "C6":"Veri Analitiği / BI", "C7":"Ekip Yönetimi & Gelişim",
 "C8":"Koordinasyon / İç Paydaş İletişimi", "C9":"Sertifika/Lisans (SPK vb.)",
 "C10":"Otomasyon / Süreç İyileştirme", "C11":"Finansal Tablo / Muhasebe / Mizan",
 "C12":"Sürdürülebilirlik / ÇSY", "C13":"Üst Yönetim / Komite Raporlama",
 "C14":"Dış Kurum / Düzenleyici İlişki", "C15":"Kredi / Dış Ticaret Ürünleri",
 "C16":"Kurumsal İletişim / Marka / Reklam", "C17":"Eğitim / Kapasite Geliştirme",
 "C18":"Sermaye Yön. / Bono İhraç / Fonlama",
}
KURALLAR_VARSAYILAN = {
 "C1":  ["müşteri", "portföy", "müşteri ilişki"],
 "C2":  ["satış", "hedef", "gelir", "penetrasyon", "pazar payı", "çapraz satış"],
 "C3":  ["mevzuat", "uyum", "yasal", "düzenleme", "prosedür", "compliance", "kvkk"],
 "C4":  ["performans", "rapor", "izle", "takip", "kpi", "yönetsel rapor"],
 "C5":  ["bütçe", "planlama", "forecast", "tahmin", "likidite"],
 "C6":  ["analitik", "veri analiz", "bi ", "dashboard", "modelleme"],
 "C7":  ["ekip", "gelişim", "koçluk", "yetkinlik"],
 "C8":  ["koordinasyon", "iletişim", "paydaş", "birim", "işbirliği", "gm birim", "şube"],
 "C9":  ["spk", "lisans", "sertifika", "düzey"],
 "C10": ["otomasyon", "süreç iyileştirme", "dijital", "verimlilik"],
 "C11": ["muhasebe", "mizan", "finansal tablo", "bilanço", "kayıt"],
 "C12": ["sürdürülebilir", "çsy", "esg", "çevre"],
 "C13": ["üst yönetim", "komite", "yönetim kurulu"],
 "C14": ["bddk", "tcmb", "düzenleyici", "dış kurum", "denetim", "resmi kurum"],
 "C15": ["kredi", "dış ticaret", "akreditif", "teminat", "ithalat", "ihracat"],
 "C16": ["reklam", "marka", "halkla ilişki", "sponsorluk", "web sitesi", "pazarlama"],
 "C17": ["eğitim", "kapasite", "program"],
 "C18": ["sermaye yönet", "bono", "ihraç", "fonlama", "hazine"],
}

# ============================================================================
# MOCK VERİ (PositionDefinition benzeri)
# ============================================================================
def mock_df() -> pd.DataFrame:
    veri = [
        ("P-SURDUR", "Sürdürülebilirlik Uzmanı",
         "Sürdürülebilirlik stratejisini belirler ve yürütür. ÇSY performansını izler, "
         "değerlendirir ve raporlar. Kurum içi sürdürülebilirlik eğitim programları düzenler. "
         "Üst yönetim ve komiteye raporlamaları hazırlar. İlgili yasal düzenlemeleri takip eder."),
        ("P-KURIL", "Kurumsal İletişim & Pazarlama Uzmanı",
         "Reklam, halkla ilişkiler ve sponsorluk aktivitelerini yürütür. Kurumsal sosyal "
         "sorumluluk ve sürdürülebilirlik içeriği üretir. İç iletişim platformunu yönetir. "
         "Web sitesi ve aylık raporları hazırlar."),
        ("P-BIREY", "Bireysel Portföy Yöneticisi",
         "Bireysel müşteri portföyünü oluşturur ve yönetir. Satış hedeflerini ve ürün "
         "penetrasyonunu artırır. Mevzuat ve banka prosedürlerine uyar. SPK Düzey 1 lisansı ile "
         "sermaye piyasası işlemleri yürütür. Şube ve GM birimleriyle koordinasyon sağlar."),
        ("P-BIREY-KID", "Kıdemli Bireysel Portföy Yöneticisi",
         "Bireysel müşteri portföyünü oluşturur, yönetir ve büyütür. Satış hedeflerini ve ürün "
         "penetrasyonunu artırır. Junior portföy yöneticilerine mentorluk yapar. Mevzuat ve banka "
         "prosedürlerine uyar. SPK Düzey 1 lisansı ile sermaye piyasası işlemleri yürütür. Şube ve "
         "GM birimleriyle koordinasyon sağlar."),
        ("P-TICPF", "Ticari Portföy Yöneticisi",
         "Ticari müşteri portföyünü yönetir ve büyütür. Satış ve gelir hedeflerine ulaşır. "
         "Kredi ve dış ticaret ürünlerini (akreditif, teminat) sunar. Mevzuata uyar ve şube "
         "birimleriyle koordinasyon sağlar."),
        ("P-MUHFT", "Muhasebe & Finansal Raporlama Uzmanı",
         "Muhasebe kayıtlarını ve mizanı tutar. Finansal tabloları ve yönetsel raporları "
         "hazırlar. Bütçe planlama sürecine veri sağlar. Mevzuata ve raporlama standartlarına uyar."),
        ("P-HAZINE", "Hazine / Fonlama Uzmanı",
         "Sermaye yönetimi, bono ihracı ve fonlama işlemlerini yürütür. Likidite ve bütçe "
         "planlamasını izler ve raporlar. Düzenleyici kurumlarla (BDDK, SPK) ilişkileri yönetir. "
         "Üst yönetim ve komiteye raporlama yapar."),
        ("P-KOBI", "KOBİ Portföy Yöneticisi",
         "KOBİ müşteri portföyünü yönetir ve satış hedeflerine ulaşır. Kredi ürünlerini sunar. "
         "Mevzuata uyar ve şube birimleriyle koordinasyon sağlar."),
        ("P-BILGI", "Veri & Analitik Uzmanı",
         "Veri analizi ve BI dashboard'ları geliştirir. Süreç otomasyonu ve dijital iyileştirme "
         "yürütür. Yönetsel raporları hazırlar."),
    ]
    return pd.DataFrame([
        dict(PositionId=pid, Summary=ad, Responsibilities=resp) for pid, ad, resp in veri])

# ============================================================================
# METİN İŞLEME + KURAL TABANLI ETİKETLEME (LLM YOK)
# ============================================================================
_TR = str.maketrans("IİĞÜŞÖÇ", "ıiğüşöç")
def tr_kucuk(s: str) -> str:
    return s.translate(_TR).lower()

_BOILERPLATE = re.compile(
    r"(üniversite mezun|ingilizce|yabancı dil|ms office|microsoft office|"
    r"lisans mezun|tercihen|iyi derecede|en az \d)", re.IGNORECASE)

def cumlelere_bol(metin) -> list[str]:
    if not isinstance(metin, str):
        return []
    t = re.sub(r"[••▪\-\*]\s+", ". ", metin)
    t = re.sub(r"[\r\n;]+", ". ", t)
    out = []
    for p in re.split(r"(?<=[.!?])\s+", t):
        p = p.strip(" .;-\t")
        if len(p) < 12 or _BOILERPLATE.search(p):
            continue
        out.append(p)
    return out

def kavram_etiketle(cumle: str, kurallar: dict) -> list[str]:
    t = tr_kucuk(cumle)
    return [kod for kod, anahtarlar in kurallar.items()
            if any(tr_kucuk(a) in t for a in anahtarlar)]

# --- Aynı pozisyonun kıdem/seviye versiyonları -------------------------------
KIDEM_ISARETLERI = [
    "kidemli", "kıdemli", "basuzman", "başuzman", "bas", "baş", "yardimcisi", "yardımcısı",
    "yardimci", "yardımcı", "uzmani", "uzmanı", "uzman", "yonetmeni", "yönetmeni",
    "yonetmen", "yönetmen", "muduru", "müdürü", "mudur", "müdür", "yoneticisi", "yöneticisi",
    "yonetici", "yönetici", "direktoru", "direktörü", "direktor", "direktör", "yetkilisi",
    "yetkili", "memuru", "memur", "sefi", "şefi", "sef", "şef", "koordinatoru", "koordinatörü",
    "koordinator", "koordinatör", "asistani", "asistanı", "asistan", "stajyer",
    "genel", "grup", "bolge", "bölge", "seviye", "kademe", "junior", "senior", "lead", "jr", "sr",
    "i", "ii", "iii", "iv", "v", "1", "2", "3", "4", "5",
]
_KIDEM_SET = set(tr_kucuk(x) for x in KIDEM_ISARETLERI)

def _kidem_taban(ad: str) -> str:
    t = re.sub(r"[^0-9a-zcgiosuçğıöşü ]", " ", tr_kucuk(ad))
    return " ".join(w for w in t.split() if w not in _KIDEM_SET).strip()

def ayni_kidem_ailesi(adA: str, adB: str) -> bool:
    a, b = _kidem_taban(adA), _kidem_taban(adB)
    return bool(a) and a == b

# ============================================================================
# BENZERLİK (ağırlıklı Jaccard) — seçilen görevler üzerinde
# ============================================================================
def kisa_ad(row) -> str:
    ad = str(row.get("Summary", "") or "").strip()
    return ad[:60] if ad and ad.lower() != "nan" else str(row["PositionId"])

def wjaccard(a: dict, b: dict) -> float:
    keys = set(a) | set(b)
    inter = sum(min(a.get(k, 0), b.get(k, 0)) for k in keys)
    union = sum(max(a.get(k, 0), b.get(k, 0)) for k in keys)
    return inter / union if union else 0.0

def analiz_et(df_secili: pd.DataFrame, concepts: dict, kurallar: dict,
              esik: float = ESIK_VARSAYILAN) -> dict:
    JOBS, WEIGHTS, cumle_detay = {}, {}, {}
    for _, row in df_secili.iterrows():
        jid = str(row["PositionId"])
        resp = [(c, kavram_etiketle(c, kurallar)) for c in cumlelere_bol(row["Responsibilities"])]
        if not resp:
            continue
        JOBS[jid] = (kisa_ad(row), resp)
        cumle_detay[jid] = resp
        w = {}
        for _, codes in resp:
            for c in codes:
                w[c] = w.get(c, 0) + 1
        WEIGHTS[jid] = w

    ids = list(JOBS)
    S = pd.DataFrame(0.0, index=ids, columns=ids)
    for a in ids:
        for b in ids:
            S.loc[a, b] = 1.0 if a == b else wjaccard(WEIGHTS[a], WEIGHTS[b])

    flagged = []
    for a, b in combinations(ids, 2):
        s = float(S.loc[a, b])
        shared = sorted(set(WEIGHTS[a]) & set(WEIGHTS[b]),
                        key=lambda k: -min(WEIGHTS[a][k], WEIGHTS[b][k]))
        flagged.append(dict(benzerlik=round(s, 4), yuzde=round(s * 100), esik_ustu=s > esik,
                            ayni_kidem=ayni_kidem_ailesi(JOBS[a][0], JOBS[b][0]),
                            gorevA=a, adA=JOBS[a][0], gorevB=b, adB=JOBS[b][0],
                            ortak_kodlar=shared, ortak_kavramlar=[concepts[k] for k in shared
                                                                  if k in concepts]))
    flagged.sort(key=lambda d: -d["benzerlik"])

    kullanilan = [c for c in concepts if any(c in WEIGHTS[j] for j in ids)]
    kavram_matrisi = pd.DataFrame(0, index=[f"{j} · {JOBS[j][0]}" for j in ids],
                                  columns=[concepts[c] for c in kullanilan])
    for j in ids:
        for c in kullanilan:
            kavram_matrisi.loc[f"{j} · {JOBS[j][0]}", concepts[c]] = WEIGHTS[j].get(c, 0)

    return dict(JOBS=JOBS, WEIGHTS=WEIGHTS, S=S, flagged=flagged,
                kavram_matrisi=kavram_matrisi, cumle_detay=cumle_detay,
                concepts=concepts, esik=esik)

# ============================================================================
# OTURUM DURUMU (mock + kural + oturum içi geri bildirim)
# ============================================================================
if "concepts" not in st.session_state:
    st.session_state.concepts = dict(CONCEPTS_VARSAYILAN)
    st.session_state.kurallar = {k: list(v) for k, v in KURALLAR_VARSAYILAN.items()}
st.session_state.setdefault("analiz", None)
st.session_state.setdefault("kavram_fb", None)
st.session_state.setdefault("rk_all", None)      # rol–kavram: tüm roller üzerinde eşleştirme (önbellek)
st.session_state.setdefault("fb_pairs", [])     # çift geri bildirimleri
st.session_state.setdefault("fb_mapping", [])    # kavram eşleştirme geri bildirimleri
st.session_state.setdefault("fb_concept", [])    # kavram önerileri

# ---- yapay zeka yorumu (opsiyonel LLM: Streamlit secrets [llm]) ----
SISTEM_KAR = (
  "Sen bir banka İK / organizasyon uzmanısın. Sana görev tanımları arasındaki benzerlik "
  "bulguları verilir: (1) İNCELENECEK çiftler (farklı pozisyon, olası çakışma), (2) AYNI "
  "POZİSYONUN KIDEM/SEVİYE versiyonları (yüksek benzerlik beklenir). Kısa, Türkçe, madde madde "
  "yorum yaz: hangileri gerçekten çakışıyor olabilir, hangileri kıdem kaynaklı normaldir, ne "
  "önerirsin. Yalnızca verilen bulgulara dayan."
)
SISTEM_RK = (
  "Sen bir banka İK / organizasyon uzmanısın. Sana roller ve eşleştikleri kavramlar verilir. "
  "Kısa, Türkçe bir yorum yaz: rollerin kavramsal odakları, örtüşmeler/boşluklar, öneriler."
)

def _ai_yorum(sistem: str, kullanici: str) -> tuple[bool, str]:
    """Streamlit secrets'ta [llm] tanımlıysa yorum üretir; değilse bilgilendirir."""
    try:
        conf = dict(st.secrets.get("llm", {}))
    except Exception:
        conf = {}
    base = str(conf.get("base_url", "")).strip()
    model = str(conf.get("model", "")).strip()
    key = str(conf.get("api_key", "")).strip()
    if not base or not model:
        return False, ("Bu demo sürümünde yapay zeka yorumu için LLM bağlı değil. "
                       "Streamlit secrets'a [llm] base_url ve model ekleyerek etkinleştirebilirsin; "
                       "kurum içi sürümde otomatik çalışır.")
    try:
        payload = {"model": model, "temperature": 0.2,
                   "messages": [{"role": "system", "content": sistem},
                                {"role": "user", "content": kullanici}]}
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        req = Request(base.rstrip("/") + "/chat/completions",
                      data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urlopen(req, timeout=60, context=ssl.create_default_context()) as r:
            d = json.loads(r.read().decode("utf-8"))
        return True, d["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return False, f"LLM'e ulaşılamadı ({type(e).__name__})."

def _yapay_zeka_kutusu(state_key: str):
    veri = st.session_state.get(state_key)
    if veri:
        (st.info if veri.get("ok") else st.warning)(
            ("" + veri["metin"]) if veri.get("ok") else veri["metin"])

def _cift_tablo(liste) -> pd.DataFrame:
    return pd.DataFrame([{
        "Benzerlik %": f["yuzde"], "Görev A": f["adA"], "Görev B": f["adB"],
        "Ortak kavramlar": ", ".join(f["ortak_kavramlar"])} for f in liste])


def _kirmizi_hucre(v):
    """matplotlib'siz kırmızı gradyan (0-100)."""
    try:
        a = max(0.0, min(1.0, float(v) / 100))
    except (TypeError, ValueError):
        return ""
    return f"background-color: rgba(220,38,38,{a:.2f}); color: {'white' if a > 0.5 else 'black'}"

def _isi_haritasi_stil(S: pd.DataFrame):
    return (S * 100).round(0).astype(int).style.map(_kirmizi_hucre).format("{}")

def _mavi_matris_stil(M: pd.DataFrame):
    """matplotlib'siz mavi gradyan (ağırlık matrisi)."""
    mx = max(1, int(M.values.max())) if M.size else 1
    def f(v):
        try:
            x = float(v)
        except (TypeError, ValueError):
            return ""
        if x <= 0:
            return ""
        return f"background-color: rgba(74,144,217,{0.15 + 0.85 * min(x, mx) / mx:.2f})"
    return M.style.map(f).format("{}")

def _eslestirme_tablo(detay, concepts) -> pd.DataFrame:
    return pd.DataFrame([{
        "Sorumluluk cümlesi": s,
        "Eşleşen kavramlar": ", ".join(concepts[c] for c in codes if c in concepts) or "—"}
        for s, codes in detay])

def _now():
    return datetime.now().isoformat(timespec="seconds")

def _csv(rows: list[dict]) -> bytes:
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig")


# ============================================================================
# BAŞLIK
# ============================================================================
st.title("Görev Tanımı Benzerlik Arayüzü — Demo")
st.caption("Streamlit Cloud demo · Veri: **mock** · Kavram etiketleme: **kural tabanlı (LLM yok)** · "
           "Geri bildirim: oturum belleği (kalıcı değil, CSV indirilebilir)")

# Görüntü sırası: Karşılaştırma · Rol–Kavram · Kavram Ontolojisi · Geri Bildirim.
# (Kod blokları sekme1=Karşılaştırma, sekme2=Geri Bildirim, sekme3=Rol–Kavram,
#  sekme4=Ontoloji; değişkenleri bloklarla eşleştirmek için 1,3,4,2 sırayla açıyoruz.)
sekme1, sekme3, sekme4, sekme2 = st.tabs([
    "1 Karşılaştırma", "2 Rol–Kavram Görünümü",
    "3 Kavram Ontolojisi (JSON)", "4 Geri Bildirim"])

df = mock_df()
etiketler = {f"{r['PositionId']} · {kisa_ad(r)}": str(r["PositionId"]) for _, r in df.iterrows()}

# ============================================================================
# EKRAN 1 — KARŞILAŞTIRMA
# ============================================================================
with sekme1:
    st.subheader("Görev tanımı karşılaştırması")
    st.write("İstediğin kadar görev tanımı seç. Önce her görev için **kavram eşleştirmeleri**, "
             "sonra aralarındaki **benzerlik matrisi** gösterilir.")
    secili_gorunen = st.multiselect("Karşılaştırılacak görev tanımları",
                                    list(etiketler.keys()), help="En az 2 görev seç.")
    esik = st.slider("Benzerlik eşiği (%)", 5, 100, int(ESIK_VARSAYILAN * 100), 5) / 100.0

    if st.button("Karşılaştır", type="primary", disabled=len(secili_gorunen) < 2):
        secili_ids = [etiketler[g] for g in secili_gorunen]
        alt = df[df["PositionId"].astype(str).isin(secili_ids)]
        st.session_state.analiz = analiz_et(alt, st.session_state.concepts,
                                            st.session_state.kurallar, esik=esik)
        st.session_state.pop("ai_kar", None)
        st.success("Analiz tamamlandı.")

    A = st.session_state.analiz
    if A:
        ids = list(A["JOBS"])
        st.markdown("### Görev bazlı kavram eşleştirmeleri")
        for jid in ids:
            with st.expander(f"{jid} · {A['JOBS'][jid][0]}", expanded=False):
                st.dataframe(_eslestirme_tablo(A["cumle_detay"][jid], A["concepts"]),
                             width="stretch", hide_index=True)
                w = A["WEIGHTS"][jid]
                if w:
                    ozet = ", ".join(f"{A['concepts'][c]} ({n})"
                                     for c, n in sorted(w.items(), key=lambda x: -x[1])
                                     if c in A["concepts"])
                    st.caption(f"Kavram ağırlıkları (cümle sayısı): {ozet}")

        st.markdown("### Benzerlik matrisi (ağırlıklı Jaccard, %)")
        st.dataframe(_isi_haritasi_stil(A["S"]), width="stretch")

        esik_ustu = [f for f in A["flagged"] if f["esik_ustu"]]
        incele = [f for f in esik_ustu if not f.get("ayni_kidem")]
        kidem = [f for f in esik_ustu if f.get("ayni_kidem")]

        st.markdown(f"#### İncelenecek çiftler (farklı pozisyon, %{int(A['esik']*100)}+)")
        if incele:
            st.dataframe(_cift_tablo(incele), width="stretch", hide_index=True)
        else:
            st.info("Farklı pozisyonlar arasında eşiği aşan çift yok.")

        st.markdown("#### Aynı pozisyon — kıdem/seviye versiyonları (beklenen)")
        if kidem:
            st.caption("Aynı işin farklı kıdem kademeleri; yüksek benzerlik beklenir, çakışma değildir.")
            st.dataframe(_cift_tablo(kidem), width="stretch", hide_index=True)
        else:
            st.caption("Aynı pozisyonun kıdem/seviye versiyonu tespit edilmedi.")

        st.divider()
        if st.button("Yapay zeka yorumu al", key="btn_ai_kar"):
            baglam = ["İNCELENECEK ÇİFTLER (farklı pozisyon):"]
            baglam += [f"- %{f['yuzde']} {f['adA']} <-> {f['adB']} | ortak: {', '.join(f['ortak_kavramlar'])}"
                       for f in incele] or ["- yok"]
            baglam += ["", "AYNI POZİSYONUN KIDEM/SEVİYE VERSİYONLARI (beklenen):"]
            baglam += [f"- %{f['yuzde']} {f['adA']} <-> {f['adB']}" for f in kidem] or ["- yok"]
            with st.spinner("Yapay zeka yorumu üretiliyor..."):
                ok, metin = _ai_yorum(SISTEM_KAR, "\n".join(baglam))
            st.session_state.ai_kar = {"ok": ok, "metin": metin}
        _yapay_zeka_kutusu("ai_kar")

        with st.expander("Tüm çift skorları + Görev × Kavram matrisi"):
            st.dataframe(pd.DataFrame([{
                "Benzerlik %": f["yuzde"], "Görev A": f["adA"], "Görev B": f["adB"],
                "Eşik üstü": "Evet" if f["esik_ustu"] else "",
                "Kıdem/seviye": "Evet" if f.get("ayni_kidem") else "",
                "Ortak kavramlar": ", ".join(f["ortak_kavramlar"])} for f in A["flagged"]]),
                width="stretch", hide_index=True)
            st.dataframe(_mavi_matris_stil(A["kavram_matrisi"]), width="stretch")

# ============================================================================
# EKRAN 2 — GERİ BİLDİRİM
# ============================================================================
with sekme2:
    st.subheader("Geri bildirim")
    kullanici = st.text_input("Kullanıcı / birim (opsiyonel)", key="fb_kullanici")
    alt1, alt2 = st.tabs(["Benzerlik çiftleri (%30+)", "Kavram eşleştirmeleri"])

    # (a) benzerlik çiftleri
    with alt1:
        A = st.session_state.analiz
        ustu = [f for f in A["flagged"] if f["esik_ustu"] and not f.get("ayni_kidem")] if A else []
        if not A:
            st.info("Önce **1 Karşılaştırma** ekranında bir analiz çalıştır.")
        elif not ustu:
            st.info("Son analizde incelenecek (farklı pozisyon) çift yok.")
        else:
            taban = pd.DataFrame([{
                "gorevA": f["gorevA"], "adA": f["adA"], "gorevB": f["gorevB"], "adB": f["adB"],
                "benzerlik": f["benzerlik"], "yuzde": f["yuzde"],
                "Görev A": f["adA"], "Görev B": f["adB"], "Benzerlik %": f["yuzde"],
                "Karar": "—", "Not": ""} for f in ustu])
            duzen = st.data_editor(
                taban[["Görev A", "Görev B", "Benzerlik %", "Karar", "Not"]],
                width="stretch", hide_index=True, key="skor_editor",
                column_config={"Karar": st.column_config.SelectboxColumn(
                    "Karar", options=["—", "Doğru", "Yanlış"], required=True),
                    "Benzerlik %": st.column_config.NumberColumn(disabled=True),
                    "Görev A": st.column_config.TextColumn(disabled=True),
                    "Görev B": st.column_config.TextColumn(disabled=True)})
            if st.button("Çift geri bildirimlerini kaydet", type="primary"):
                n = 0
                for i, row in duzen.iterrows():
                    if row["Karar"] in ("Doğru", "Yanlış"):
                        t = taban.iloc[i]
                        st.session_state.fb_pairs.append(dict(
                            zaman=_now(), kullanici=kullanici, gorevA=t["gorevA"], adA=t["adA"],
                            gorevB=t["gorevB"], adB=t["adB"], yuzde=int(t["yuzde"]),
                            karar=row["Karar"], not_metni=row["Not"]))
                        n += 1
                st.success(f"{n} geri bildirim kaydedildi (oturum belleği)." if n else "İşaretli satır yok.")

        st.markdown("##### Toplanan çift geri bildirimleri (oturum)")
        if st.session_state.fb_pairs:
            st.dataframe(pd.DataFrame(st.session_state.fb_pairs), width="stretch", hide_index=True)
            st.download_button("CSV indir", _csv(st.session_state.fb_pairs),
                               "skor_geri_bildirim.csv", "text/csv", key="dl_skor")
        else:
            st.caption("Henüz kayıt yok.")

    # (b) kavram eşleştirmeleri
    with alt2:
        st.write("Herhangi bir görev için kavram eşleştirmesini görüntüle; doğruluğunu değerlendir, "
                 "**beklenen eşleştirmeyi** yaz ya da **silinecek kavramı** belirt.")
        secim = st.selectbox("Görev tanımı", list(etiketler.keys()), key="kv_fb_secim")
        if st.button("Kavram eşleştirmesini göster"):
            jid = etiketler[secim]
            alt = df[df["PositionId"].astype(str) == jid]
            R = analiz_et(alt, st.session_state.concepts, st.session_state.kurallar)
            detay = R["cumle_detay"].get(jid, [])
            st.session_state.kavram_fb = dict(jid=jid, ad=R["JOBS"].get(jid, (jid,))[0],
                                              tablo=_eslestirme_tablo(detay, R["concepts"]).to_dict("records"))
        fb = st.session_state.kavram_fb
        if fb:
            st.markdown(f"**{fb['jid']} · {fb['ad']}** — mevcut kavram eşleştirmesi")
            st.dataframe(pd.DataFrame(fb["tablo"]), width="stretch", hide_index=True)
            with st.form("kavram_es_fb", clear_on_submit=True):
                karar = st.radio("Bu eşleştirme doğru mu?", ["Doğru", "Yanlış"], horizontal=True)
                beklenen = st.text_area("Beklenen eşleştirme (opsiyonel)")
                silinecek = st.text_input("Silinmesini istediğin kavram(lar) (opsiyonel)")
                aciklama = st.text_area("Açıklama / not (opsiyonel)")
                if st.form_submit_button("Kavram eşleştirme geri bildirimini kaydet", type="primary"):
                    st.session_state.fb_mapping.append(dict(
                        zaman=_now(), kullanici=kullanici, gorev=fb["jid"], ad=fb["ad"],
                        mevcut_eslestirme=json.dumps(fb["tablo"], ensure_ascii=False),
                        karar=karar, beklenen_eslestirme=beklenen,
                        silinecek_kavram=silinecek, aciklama=aciklama))
                    st.success("Kaydedildi (oturum belleği).")

        st.markdown("##### Toplanan kavram eşleştirme geri bildirimleri (oturum)")
        if st.session_state.fb_mapping:
            st.dataframe(pd.DataFrame(st.session_state.fb_mapping), width="stretch", hide_index=True)
            st.download_button("CSV indir", _csv(st.session_state.fb_mapping),
                               "kavram_eslestirme_geri_bildirim.csv", "text/csv", key="dl_ke")
        else:
            st.caption("Henüz kayıt yok.")

# ============================================================================
# EKRAN 3 — ROL–KAVRAM GÖRÜNÜMÜ
# ============================================================================
with sekme3:
    st.subheader("Rol – Kavram")
    st.write("Bir kavram seç; o kavramla ilişkili roller ve ilgili sorumluluk cümleleri listelenir.")

    concepts = st.session_state.concepts
    aranan = st.selectbox("Kavram", ["—"] + sorted(concepts.values()), key="rk_kavram_sec")
    if aranan != "—":
        # kavram eşleştirmesini tüm roller üzerinde hesapla (oturumda önbelleğe al)
        if st.session_state.get("rk_all") is None:
            st.session_state.rk_all = analiz_et(df, concepts, st.session_state.kurallar)
        R = st.session_state.rk_all
        kod = next((c for c in R["concepts"] if R["concepts"][c] == aranan), None)
        satir = [{"Rol": f"{jid} · {R['JOBS'][jid][0]}", "İlgili sorumluluk cümlesi": sent}
                 for jid in R["JOBS"] for sent, codes in R["cumle_detay"][jid]
                 if kod and kod in codes]
        if satir:
            st.caption(f"**{aranan}** — {len(satir)} sorumluluk cümlesiyle ilişkili:")
            st.dataframe(pd.DataFrame(satir), width="stretch", hide_index=True)
        else:
            st.info("Bu kavramla ilişkili sorumluluk cümlesi bulunamadı.")

# ============================================================================
# EKRAN 4 — KAVRAM ONTOLOJİSİ (JSON düzenleme, oturum içi + indir)
# ============================================================================
with sekme4:
    st.subheader("Kavram ontolojisi (JSON)")
    st.write("Kavram ontolojisini düzenle. İki alana da (kavramlar ve kurallar) satır ekleyebilir, "
             "mevcutları değiştirebilirsin. **JSON'ı Güncelle** oturumda geçerli olur; kalıcı "
             "kaydetmek için JSON'u indirip repodaki dosyayla değiştir.")

    concepts = st.session_state.concepts
    kurallar = st.session_state.kurallar
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Kavramlar (CONCEPTS)")
        kdf = pd.DataFrame([{"Kod": k, "Kavram": v} for k, v in concepts.items()])
        kdf_yeni = st.data_editor(kdf, width="stretch", hide_index=True,
                                  num_rows="dynamic", key="concept_editor")
    with col2:
        st.markdown("#### Kavram kuralları (KAVRAM_KURALLARI)")
        rdf = pd.DataFrame([{"Kod": k, "Anahtar kelimeler (virgülle)": ", ".join(v)}
                            for k, v in kurallar.items()])
        rdf_yeni = st.data_editor(rdf, width="stretch", hide_index=True,
                                  num_rows="dynamic", key="rule_editor")

    if st.button("JSON'ı Güncelle", type="primary"):
        yeni_concepts = {str(r["Kod"]).strip(): str(r["Kavram"]).strip()
                         for _, r in kdf_yeni.iterrows()
                         if str(r.get("Kod", "")).strip() and str(r.get("Kavram", "")).strip()}
        yeni_kurallar = {}
        for _, r in rdf_yeni.iterrows():
            kod = str(r.get("Kod", "")).strip()
            if not kod:
                continue
            yeni_kurallar[kod] = [x.strip() for x in
                                  str(r.get("Anahtar kelimeler (virgülle)", "")).split(",") if x.strip()]
        if not yeni_concepts:
            st.error("En az bir kavram gerekli.")
        else:
            eklenen = set(yeni_concepts) - set(concepts)
            st.session_state.concepts = yeni_concepts
            st.session_state.kurallar = yeni_kurallar
            st.session_state.rk_all = None   # ontoloji değişti -> rol–kavram önbelleğini sıfırla
            for kod in eklenen:
                st.session_state.fb_concept.append(dict(
                    zaman=_now(), tur="yeni_kavram", kod=kod, ad=yeni_concepts[kod]))
            st.success(f"JSON güncellendi (oturum). {len(yeni_concepts)} kavram ({len(eklenen)} yeni). "
                       "Kalıcı olması için aşağıdan indirip repodaki dosyayla değiştir.")

    icerik = json.dumps({"CONCEPTS": st.session_state.concepts,
                         "KAVRAM_KURALLARI": st.session_state.kurallar}, ensure_ascii=False, indent=2)
    with st.expander("Güncel JSON'u görüntüle / indir"):
        st.code(icerik, language="json")
    st.download_button("kavram_ontolojisi_llm.json indir", icerik.encode("utf-8"),
                       "kavram_ontolojisi_llm.json", "application/json", key="dl_json")

    st.divider()
    st.markdown("#### Serbest öneri / geri bildirim")
    with st.form("kavram_oneri", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        tur = c1.selectbox("Tür", ["yeni_kavram", "yeni_kural", "duzenleme", "oneri"])
        kod = c2.text_input("Kod (örn. C19)")
        ad = c3.text_input("Kavram adı")
        anahtar = st.text_input("Anahtar kelime(ler) — virgülle")
        aciklama = st.text_area("Açıklama / gerekçe")
        if st.form_submit_button("Öneriyi gönder"):
            st.session_state.fb_concept.append(dict(
                zaman=_now(), tur=tur, kod=kod, ad=ad, anahtar_kelime=anahtar, aciklama=aciklama))
            st.success("Öneri kaydedildi (oturum belleği).")

    if st.session_state.fb_concept:
        with st.expander("Toplanan kavram önerileri (oturum)"):
            st.dataframe(pd.DataFrame(st.session_state.fb_concept), width="stretch", hide_index=True)
            st.download_button("CSV indir", _csv(st.session_state.fb_concept),
                               "kavram_onerileri.csv", "text/csv", key="dl_oneri")
