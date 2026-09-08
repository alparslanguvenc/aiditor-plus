# AI-ditor Plus görsel kimliği

Sade bir A monogramı ve üstte küçük bir artı işareti. Akademik yayıncılığın tipografik dilini taşıyan simge; arayüz, macOS ve Windows paketlerinde aynıdır.

| Kullanım | Renk |
|---|---|
| Zemin | Lacivert `#153449` |
| A monogramı | Kırık beyaz `#F7F5EF` |
| Artı işareti | Açık yeşil `#88C9BD` |

Ana kaynak: [`static/brand.svg`](../static/brand.svg). Yazı tipi veya dış kaynağa bağlı değildir; tüm çizgiler vektör yollarıdır. Kenarlar dışında gerçek saydamlık vardır. Gölge, doku ve degrade kullanılmaz. Simgedeki boşluğu koruyun; yatay veya dikey esnetmeyin.

Üretim dosyaları: `aiditor_plus_icon.png` (1024 px), `icon_plus.icns` (macOS), `icon_plus.ico` (Windows). SVG değiştirildiğinde bu dosyaları yeniden üretin:

```sh
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python scripts/export_brand.py
```

Logo taslağı yerleşik görsel üretim aracıyla hazırlandı; uygulamanın son varlıkları aynı tasarımın düzenlenebilir SVG kaynağından oluşturuldu. Tasarım özeti: lacivert yuvarlatılmış kare üzerinde kırık beyaz, akademik tipografiyle çizilmiş A ve küçük yeşil artı; sade, düz renkli, küçük boyutlarda okunabilir; ek yazı, doku veya üç boyutlu efekt yok.

Bu varlıklar da deponun MIT lisansı kapsamındadır.
