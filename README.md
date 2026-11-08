# Radar Kıbrıs – RSS Bridge

GitHub Actions ile **yaklaşık** 5 dakikada bir RSS kaynaklarını kontrol eder, ana görseli ve izinli tam metni/özetleri RSS 2.0 XML'e dönüştürür. Gazisoft V8'de editör onaylı haber havuzuna bağlanması hedeflenir. Gazisoft uyumluluğu henüz gerçek panelde doğrulanmamıştır.

## Kurulum
1. GitHub'da **public** `radar-rss-bot` adlı boş depo açın. Bu klasörün **içeriğini** (gizli `.github` klasörü dahil) yükleyin.
2. `sources.yml` içindeki `feed` URL'lerini kaynakların resmi RSS sayfalarından doğrulayın. Kıbrıs Postası, Ensonhaber ve TAK boş/kapalıdır; yanlış adres varsayılmamıştır. Havadis `/feed/` adresi olası WordPress uç noktasıdır, çalıştığı doğrulanmamıştır.
3. GitHub → Actions → `Radar RSS Bridge` → `Run workflow` ile ilk çalıştırmayı yapın. `docs/status.json` raporunu inceleyin.
4. Settings → Pages → Build and deployment → **Deploy from a branch**, `main`, `/docs` → Save.
5. Birkaç dakika sonra `https://KULLANICI.github.io/radar-rss-bot/havadis.xml` gibi XML bağlantılarını açın. KULLANICI yerine GitHub kullanıcı adınızı yazın.
6. Gazisoft → Özel RSS Ajanı bölümüne XML adreslerini tek tek ekleyin. Yayın modunu **haber havuzu / editör onayı** olarak ayarlayın. Gerçek Gazisoft testinde `content:encoded`, `enclosure`, görsel ve tekrar davranışını doğrulayın.

## Çalışma mantığı
- RSS'ten haberleri okur, bağlantıdan sayfayı ziyaret ederek `og:image` / `media:*` görseli arar.
- `full_text: false` varsayılanı RSS özetini aktarır. **Yalnızca yeniden yayınlama izni olan kaynaklar** için `full_text: true` yapın; bu mod Trafilatura ile tam metin çıkarır.
- Eksik metin veya görsel içeren haberler XML'e eklenmez; `docs/status.json` içinde hata nedeni görünür.
- `data/*.json` önceki haberleri tutar; aynı URL tekrar eklenmez. Son 60 haber tutulur.
- Kaynak RSS bozulursa önceki başarılı XML korunur; hata raporlanır.
- Zamanlama kesin değildir; GitHub Actions yoğun saatlerde gecikebilir veya atlayabilir. 5 dakikalık cron bir hedef, SLA değildir.
- GitHub Pages **public** içerik yayımlar. İçerikleri izinli kaynaklarla sınırlayın. Görseller kaynak sunucuda kalır; hotlink engeli varsa Gazisoft görsel alamayabilir.
- TAK gibi ajanslar için abonelik/lisans koşullarını kontrol edin. Bu paket erişim engeli aşmaz.

## Yeni kaynak ekleme
`sources.yml` içine yeni bir `id`, `name`, `feed`, `enabled: true`, `full_text: false` bloğu ekleyin.

## Yerel test
`python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && python bot.py`
Windows: `.venv\\Scripts\\activate`.

## Bilinen sınırlar
- Gazisoft'un XML formatı ve özel RSS ajanı gerçek panelde test edilmedi.
- Bazı haber siteleri JavaScript, bot engeli veya robots politikası nedeniyle alınamayabilir.
- `enclosure` image/jpeg olarak verilir; PNG/WebP kaynaklarda Gazisoft tarafında doğrulama gerekebilir.
- Bu bir editör onaylı toplama sistemi; haberleri kendi başına Gazisoft'ta yayımlamaz.
